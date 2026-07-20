# ============================================================
# 가상 스포츠 OTT 데이터 생성 v3 → SQLite 적재
# v2 대비 변경:
#   - purchases 테이블 신설: 결제 이벤트 단위 (한 유저가 여러 번 결제 가능)
#   - 최초/복귀 구분: 해지 유저의 일부가 재결제(복귀)
#   - 권종 확장: 자사 플랜 + 가상의 제휴 채널 (포털A, 통신사B 등)
# 실행하면 portfolio.db를 새로 만듭니다 (기존 테이블 덮어씀)
# ============================================================

import sqlite3
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
PERIOD_START = pd.Timestamp("2025-01-01")
PERIOD_END   = pd.Timestamp("2026-07-19")
TODAY        = pd.Timestamp("2026-07-20")

# ------------------------------------------------------------
# 1) matches: 카테고리별 시즌/빈도 반영 경기 일정 (v2와 동일)
# ------------------------------------------------------------
SCHEDULE = {
    "baseball":   dict(months=[3,4,5,6,7,8,9,10],       per_week=5.0, base_w=3.0),
    "soccer":     dict(months=[1,2,3,4,5,8,9,10,11,12], per_week=3.0, base_w=2.5),
    "golf":       dict(months=list(range(1,13)),        per_week=1.0, base_w=1.2),
    "ufc":        dict(months=list(range(1,13)),        per_week=0.4, base_w=2.0),
    "basketball": dict(months=[1,2,3,4,10,11,12],       per_week=3.0, base_w=1.5),
    "volleyball": dict(months=[1,2,3,10,11,12],         per_week=2.0, base_w=1.0),
}
TEAMS = {
    "baseball":   ["서울 유니콘스", "인천 드래곤스", "부산 샤크스", "대전 이글렛츠", "광주 피닉스", "수원 재규어스"],
    "soccer":     ["FC 한강", "인천 유나이티드FC", "남산 시티", "해운대 FC", "전주 로버스", "제주 아일랜더스"],
    "basketball": ["서울 썬더", "고양 스타즈", "울산 웨이브", "창원 나이츠"],
    "volleyball": ["대전 스파이커스", "화성 점퍼스", "김천 세터스", "의정부 블록스"],
}

rows, match_id = [], 1
for week_start in pd.date_range(PERIOD_START, PERIOD_END, freq="W-MON"):
    for cat, cfg in SCHEDULE.items():
        if week_start.month not in cfg["months"]:
            continue
        for _ in range(rng.poisson(cfg["per_week"])):
            d = week_start + pd.Timedelta(days=int(rng.integers(0, 7)))
            if d > PERIOD_END:
                continue
            is_big = rng.random() < 0.10
            if cat in TEAMS:
                home, away = rng.choice(TEAMS[cat], 2, replace=False)
                title = f"{home} vs {away}"
            elif cat == "golf":
                title = f"골프 투어 {d.strftime('%m월 %W주차')} 대회"
            else:
                title = f"파이트 나이트 {match_id}"
            if is_big:
                title += " ★빅매치"
            rows.append((match_id, d, cat, title, int(is_big)))
            match_id += 1

matches = pd.DataFrame(rows, columns=["match_id", "match_date", "category", "title", "is_big_match"])
match_w = matches["category"].map(lambda c: SCHEDULE[c]["base_w"]).values \
          * np.where(matches["is_big_match"] == 1, 3.0, 1.0)
match_w = match_w / match_w.sum()
match_dates = matches["match_date"].values  # datetime64

# ------------------------------------------------------------
# 2) 권종(product) 정의: 판매 채널 × 플랜
#    ※ 제휴사는 전부 가상의 이름 (포털A, 통신사B 등)
# ------------------------------------------------------------
PRODUCTS = ["자사프리미엄", "자사베이직", "자사연간",
            "포털A프리미엄", "포털A베이직", "통신사B번들", "기타"]

def assign_products(n):
    channel = rng.choice(["자사", "포털A", "통신사B", "기타"], n, p=[0.62, 0.20, 0.10, 0.08])
    out = np.empty(n, dtype=object)
    m = channel == "자사"
    out[m] = rng.choice(["자사프리미엄", "자사베이직", "자사연간"], m.sum(), p=[0.35, 0.55, 0.10])
    m = channel == "포털A"
    out[m] = rng.choice(["포털A프리미엄", "포털A베이직"], m.sum(), p=[0.40, 0.60])
    out[channel == "통신사B"] = "통신사B번들"
    out[channel == "기타"] = "기타"
    return out

# 권종별 해지 성향 (연간은 낮고, 번들은 높게)
CHURN_ADJ = {"자사프리미엄": -0.05, "자사베이직": 0.08, "자사연간": -0.15,
             "포털A프리미엄": -0.02, "포털A베이직": 0.08, "통신사B번들": 0.12, "기타": 0.05}

def simulate_end(start_dates, products, base=0.32):
    """구독 종료 시뮬레이션 → (해지여부, 종료일: 미해지는 NaT)"""
    p = np.array([base + CHURN_ADJ[x] for x in products])
    churned = rng.random(len(products)) < p
    ends = pd.Series(start_dates) + pd.to_timedelta(rng.integers(7, 300, len(products)), unit="D")
    ends = ends.where(pd.Series(churned), pd.NaT)
    future = (ends > TODAY).fillna(False)
    churned = churned & ~future.values
    ends = ends.where(~future, pd.NaT)
    return churned, ends

# ------------------------------------------------------------
# 3) 최초 결제: 65%는 경기를 보려고 결제 (경기별 신규 판매)
# ------------------------------------------------------------
N_USERS = 10_000

attributed = rng.random(N_USERS) < 0.65
first_dates = np.empty(N_USERS, dtype="datetime64[D]")
first_trigger = np.full(N_USERS, np.nan)

idx = np.where(attributed)[0]
picked = rng.choice(len(matches), size=len(idx), p=match_w)
first_dates[idx] = match_dates[picked].astype("datetime64[D]") \
                   - rng.integers(0, 4, len(idx)).astype("timedelta64[D]")
first_trigger[idx] = matches["match_id"].values[picked]

idx = np.where(~attributed)[0]
first_dates[idx] = (PERIOD_START.to_datetime64()
                    + rng.integers(0, (PERIOD_END - PERIOD_START).days, len(idx))
                      .astype("timedelta64[D]"))

first_dates = pd.Series(pd.to_datetime(first_dates)).clip(lower=PERIOD_START)
first_products = assign_products(N_USERS)
first_churned, first_ends = simulate_end(first_dates, first_products)

acq_channels = rng.choice(
    ["organic", "paid_ads", "crm_push", "crm_email", "referral"],
    N_USERS, p=[0.35, 0.30, 0.15, 0.10, 0.10],
)

# ------------------------------------------------------------
# 4) 복귀 결제: 해지자의 25%가 재결제 (그중 80%는 경기가 계기)
# ------------------------------------------------------------
ret_rows = []  # (user_id, date, product, trigger_id)
for i in np.where(first_churned)[0]:
    if rng.random() >= 0.25:
        continue
    end = first_ends.iloc[i]
    earliest = end + pd.Timedelta(days=14)
    if earliest > PERIOD_END:
        continue
    trigger, ret_date = None, None
    if rng.random() < 0.80:  # 경기 계기 복귀
        ok = np.where(match_dates >= earliest.to_datetime64())[0]
        if len(ok) > 0:
            w = match_w[ok] / match_w[ok].sum()
            j = int(rng.choice(ok, p=w))
            ret_date = matches["match_date"].iloc[j] - pd.Timedelta(days=int(rng.integers(0, 3)))
            ret_date = max(ret_date, earliest)
            trigger = int(matches["match_id"].iloc[j])
    if ret_date is None:  # 일반 복귀
        span = (PERIOD_END - earliest).days
        ret_date = earliest + pd.Timedelta(days=int(rng.integers(0, max(span, 1))))
    product = first_products[i] if rng.random() < 0.70 else assign_products(1)[0]
    ret_rows.append((i + 1, ret_date, product, trigger))

ret_df = pd.DataFrame(ret_rows, columns=["user_id", "purchase_date", "product", "trigger_match_id"])
ret_churned, ret_ends = simulate_end(ret_df["purchase_date"], ret_df["product"].values, base=0.25)

# ------------------------------------------------------------
# 5) 테이블 조립: purchases / users / matches
# ------------------------------------------------------------
purchases = pd.concat([
    pd.DataFrame({
        "user_id": np.arange(1, N_USERS + 1),
        "purchase_date": first_dates,
        "product": first_products,
        "purchase_type": "최초",
        "trigger_match_id": pd.Series(first_trigger).astype("Int64"),
        "end_date": first_ends,
    }),
    pd.DataFrame({
        "user_id": ret_df["user_id"],
        "purchase_date": ret_df["purchase_date"],
        "product": ret_df["product"],
        "purchase_type": "복귀",
        "trigger_match_id": ret_df["trigger_match_id"].astype("Int64"),
        "end_date": ret_ends,
    }),
], ignore_index=True).sort_values(["user_id", "purchase_date"]).reset_index(drop=True)
purchases.insert(0, "purchase_id", np.arange(1, len(purchases) + 1))

last = purchases.groupby("user_id").tail(1)
status = np.where(last["end_date"].isna(), "active", "churned")
users = pd.DataFrame({
    "user_id": last["user_id"].values,
    "first_signup_date": first_dates.dt.strftime("%Y-%m-%d"),
    "acquisition_channel": acq_channels,
    "current_status": status,
}).sort_values("user_id")

# ------------------------------------------------------------
# 6) viewing_logs: 결제 건별 활성 구간 내 시청 발생
# ------------------------------------------------------------
CATEGORIES = list(SCHEDULE.keys())
CAT_P   = [0.32, 0.24, 0.16, 0.12, 0.10, 0.06]
DEVICES = ["mobile", "tv", "pc", "tablet"]
DEV_P   = [0.50, 0.28, 0.15, 0.07]

logs = []
for _, p in purchases.iterrows():
    start = p["purchase_date"]
    end = p["end_date"] if pd.notna(p["end_date"]) else TODAY
    active_days = max((end - start).days, 1)
    n = rng.poisson(lam=active_days / rng.uniform(2, 8))
    if n == 0:
        continue
    dates = start + pd.to_timedelta(rng.integers(0, active_days, n), unit="D")
    logs.append(pd.DataFrame({
        "user_id": p["user_id"],
        "view_date": dates.strftime("%Y-%m-%d"),
        "content_category": rng.choice(CATEGORIES, n, p=CAT_P),
        "device": rng.choice(DEVICES, n, p=DEV_P),
        "watch_minutes": np.clip(rng.normal(85, 40, n), 5, 240).astype(int),
    }))
viewing_logs = pd.concat(logs, ignore_index=True)
viewing_logs.insert(0, "log_id", np.arange(1, len(viewing_logs) + 1))

# 날짜 컬럼 문자열화 후 적재
purchases_out = purchases.copy()
purchases_out["purchase_date"] = purchases_out["purchase_date"].dt.strftime("%Y-%m-%d")
purchases_out["end_date"] = purchases_out["end_date"].dt.strftime("%Y-%m-%d")
matches_out = matches.copy()
matches_out["match_date"] = matches_out["match_date"].dt.strftime("%Y-%m-%d")

conn = sqlite3.connect("portfolio.db")
users.to_sql("users", conn, if_exists="replace", index=False)
matches_out.to_sql("matches", conn, if_exists="replace", index=False)
purchases_out.to_sql("purchases", conn, if_exists="replace", index=False)
viewing_logs.to_sql("viewing_logs", conn, if_exists="replace", index=False)

print(f"users {len(users):,} / matches {len(matches):,} / "
      f"purchases {len(purchases):,} (최초 {N_USERS:,} + 복귀 {len(ret_df):,}) / "
      f"viewing_logs {len(viewing_logs):,}행 적재 완료\n")

print("[권종 × 최초/복귀 결제 수]")
print(pd.crosstab(purchases["product"], purchases["purchase_type"]).to_string())
conn.close()
