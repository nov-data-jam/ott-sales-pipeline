# ============================================================
# daily_match_sales.csv → Google Sheets 자동 업로드
# 사전 준비: 서비스 계정 credentials.json + 시트에 편집자 공유
# ============================================================

import pandas as pd
import gspread

SHEET_NAME = "OTT 대시보드 원본"   # 업로드 대상 스프레드시트 이름

df = pd.read_csv("daily_match_sales.csv")

gc = gspread.service_account(filename="credentials.json")
ws = gc.open(SHEET_NAME).sheet1

ws.clear()
ws.update(
    [df.columns.tolist()] + df.astype(str).values.tolist(),
    value_input_option="USER_ENTERED",  # 숫자를 숫자 타입으로 인식시키기 위함
)
print(f"업로드 완료: {len(df):,}행 × {len(df.columns)}열")
