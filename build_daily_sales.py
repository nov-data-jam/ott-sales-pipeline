# ============================================================
# 일자 × 경기 × 권종별 신규 판매량 가공 (Looker Studio 원본 시트 포맷)
# 입력: portfolio.db (generate_ott_data_v3.py 실행 후)
# 출력: daily_match_sales.csv + 화면 미리보기
# ============================================================

import sqlite3
import pandas as pd

PRODUCTS = ["자사프리미엄", "자사베이직", "자사연간",
            "포털A프리미엄", "포털A베이직", "통신사B번들", "기타"]

conn = sqlite3.connect("portfolio.db")

# ------------------------------------------------------------
# 1) 추출: 결제 이벤트 + 귀속 경기 정보
# ------------------------------------------------------------
query = """
SELECT
    p.purchase_date                       AS 날짜,
    p.trigger_match_id                    AS match_id,
    m.title                               AS 경기명,
    m.category                            AS 종목,
    m.match_date                          AS 경기일,
    p.purchase_type,
    p.product
FROM purchases p
LEFT JOIN matches m ON p.trigger_match_id = m.match_id
"""
df = pd.read_sql(query, conn)
conn.close()

# 경기 미귀속(일반 결제)도 행으로 보이게 처리
df["경기명"] = df["경기명"].fillna("(경기 미귀속)")
df["종목"] = df["종목"].fillna("-")
df["경기일"] = df["경기일"].fillna("-")

# ------------------------------------------------------------
# 2) 가공: 일자 × 경기 단위로 권종×최초/복귀 컬럼 피벗 (wide 포맷)
# ------------------------------------------------------------
df["권종컬럼"] = df["purchase_type"] + df["product"]

wide = (
    df.groupby(["날짜", "경기명", "종목", "경기일"])["권종컬럼"]
      .value_counts()
      .unstack(fill_value=0)
      .reset_index()
)

# 컬럼 순서 고정: 최초/복귀 × 권종 (없는 조합은 0으로 생성)
ordered_cols = [f"{t}{p}" for p in PRODUCTS for t in ["최초", "복귀"]]
for c in ordered_cols:
    if c not in wide.columns:
        wide[c] = 0

wide["총이용권수"] = wide[ordered_cols].sum(axis=1)
wide = wide[["날짜", "경기명", "종목", "경기일", "총이용권수"] + ordered_cols]
wide = wide.sort_values(["날짜", "총이용권수"], ascending=[True, False]).reset_index(drop=True)

# ------------------------------------------------------------
# 3) 출력: CSV 저장 (엑셀에서 한글 안 깨지게 utf-8-sig)
# ------------------------------------------------------------
wide.to_csv("daily_match_sales.csv", index=False, encoding="utf-8-sig")
print(f"daily_match_sales.csv 저장 완료 — {len(wide):,}행 × {len(wide.columns)}열\n")

print("[최근 7일 · 경기별 신규 판매 상위 10]")
recent = wide[wide["날짜"] >= "2026-07-13"]
cols = ["날짜", "경기명", "종목", "총이용권수", "최초자사베이직", "복귀자사베이직", "최초자사프리미엄"]
print(recent.nlargest(10, "총이용권수")[cols].to_string(index=False))

print("\n[일자별 신규 판매 합계 (최근 7일)]")
print(recent.groupby("날짜")["총이용권수"].sum().to_string())
