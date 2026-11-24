# 대시보드 미리보기 이미지 생성 (README용)
# 입력: portfolio.db / 출력: dashboard.png
import sqlite3, pandas as pd, matplotlib.pyplot as plt
from matplotlib import font_manager

names = {f.name for f in font_manager.fontManager.ttflist}
for f in ["Malgun Gothic", "Noto Sans CJK KR", "Noto Sans CJK JP"]:
    if f in names:
        plt.rcParams["font.family"] = f; break
plt.rcParams["axes.unicode_minus"] = False

SURF, INK, SUB, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
BLUE, ORANGE = "#2a78d6", "#eb6834"

conn = sqlite3.connect("portfolio.db")
p = pd.read_sql("""SELECT p.purchase_date, p.purchase_type, p.trigger_match_id, m.title, m.match_date
                   FROM purchases p LEFT JOIN matches m ON p.trigger_match_id = m.match_id""", conn)
conn.close()
p["월"] = p["purchase_date"].str[:7]

total = len(p); first = (p.purchase_type == "최초").sum(); ret = (p.purchase_type == "복귀").sum()
attr = p.trigger_match_id.notna().mean()

monthly = p.groupby(["월", "purchase_type"]).size().unstack(fill_value=0)
_m = p.dropna(subset=["title"])
_m = _m.assign(label=_m["title"].str.replace(" ★빅매치", " ★", regex=False) + " (" + _m["match_date"].str[2:].str.replace("-", ".") + ")")
top = _m.groupby("label").size().nlargest(10).sort_values()

fig = plt.figure(figsize=(16, 10), facecolor=SURF)
fig.text(0.04, 0.95, "OTT 경기별 신규 판매 대시보드 (미리보기)", fontsize=22, fontweight="bold", color=INK)
fig.text(0.04, 0.915, "기간 2025-01-01 ~ 2026-07-19  ·  가상 데이터  ·  Python(matplotlib)으로 그린 미리보기",
         fontsize=12, color=SUB)

kpis = [("총 신규 판매", f"{total:,}건"), ("최초 결제", f"{first:,}건"),
        ("복귀 결제", f"{ret:,}건"), ("경기 귀속률", f"{attr:.1%}")]
for i, (lab, val) in enumerate(kpis):
    ax = fig.add_axes([0.04 + i * 0.235, 0.74, 0.215, 0.13])
    ax.set_facecolor("white"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.text(0.06, 0.70, lab, fontsize=13, color=SUB, transform=ax.transAxes)
    ax.text(0.06, 0.22, val, fontsize=28, fontweight="bold", color=INK, transform=ax.transAxes)

# 월별 추이
ax = fig.add_axes([0.05, 0.08, 0.50, 0.56], facecolor=SURF)
x = range(len(monthly))
for col, c in [("최초", BLUE), ("복귀", ORANGE)]:
    ax.plot(x, monthly[col], color=c, lw=2, marker="o", ms=5, label=col)
    ax.text(len(monthly) - 1 + 0.3, monthly[col].iloc[-1], col, color=SUB, fontsize=11, va="center")
ax.set_xticks(list(x)[::2], [m[2:].replace("-", ".") for m in monthly.index[::2]], color=SUB, fontsize=10)
ax.tick_params(axis="y", colors=SUB, labelsize=10)
ax.set_title("월별 신규 판매 (최초 vs 복귀)", loc="left", fontsize=15, color=INK, pad=12)
ax.text(1.0, 1.02, "※ 2026.07은 19일까지", transform=ax.transAxes, fontsize=10, color=MUTED, va="bottom", ha="right")
ax.grid(axis="y", color=GRID); ax.set_axisbelow(True)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
for s in ["left", "bottom"]:
    ax.spines[s].set_color(GRID)
ax.legend(frameon=False, loc="upper left", fontsize=11, labelcolor=SUB)
ax.set_xlim(-0.5, len(monthly) + 0.8)

# 경기별 순위
ax = fig.add_axes([0.75, 0.08, 0.22, 0.56], facecolor=SURF)
ax.barh(range(len(top)), top.values, color=BLUE, height=0.62)
ax.set_yticks(range(len(top)), list(top.index), fontsize=10, color=INK)
for i, v in enumerate(top.values):
    ax.text(v + 0.8, i, f"{v}", va="center", fontsize=10, color=SUB)
ax.set_title("경기별 신규 판매 TOP 10 (★ 빅매치)", loc="left", fontsize=15, color=INK, pad=12)
ax.set_xticks([])
for s in ["top", "right", "bottom"]:
    ax.spines[s].set_visible(False)
ax.spines["left"].set_color(GRID)
ax.set_xlim(0, top.max() * 1.15)

fig.savefig("dashboard.png", dpi=110, facecolor=SURF)
print(total, first, ret, attr)
