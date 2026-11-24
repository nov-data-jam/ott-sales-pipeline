# OTT Sales Pipeline 📊

스포츠 OTT 구독 서비스의 **"경기별 신규 판매량" 리포팅을 데이터 추출부터 대시보드 반영까지 자동화한 개인 프로젝트**입니다.

실무에서 `SQL 추출 → 엑셀 가공 → 스프레드시트 수동 업데이트 → Looker Studio 수치 반영`으로 반복하던 리포팅 프로세스를, 개인 환경에서 Python 파이프라인으로 재현했습니다. 모든 데이터는 구독 서비스의 데이터 구조를 직접 설계해 생성한 가상 데이터이며, 실제 서비스 데이터는 사용하지 않았습니다.

> Read the Data. Move the User.

## 파이프라인 구조

```
[데이터 생성]          [추출·가공]              [업로드]            [시각화]
generate_ott_data_v3  →  build_daily_sales   →  upload_to_sheets  →  Looker Studio
(가상 데이터 → SQLite)   (SQL 추출 + pandas 피벗)  (gspread 자동 업로드)   (자동 갱신)
```

- **데이터 생성**: 구독자 1만 명, 경기 일정 842건, 결제 이벤트(최초/복귀), 시청 로그 53만 행을 시뮬레이션하여 SQLite에 적재
- **추출·가공**: SQL로 결제-경기 데이터를 조인 추출 후, `일자 × 경기 × 권종(최초/복귀)` wide 포맷으로 피벗
- **업로드**: gspread + 서비스 계정으로 Google Sheets에 자동 반영 → 연동된 Looker Studio 대시보드가 자동 갱신

## 데이터 설계 포인트

구독형 OTT 서비스의 범용적인 판매 데이터 특성을 반영하여 설계했습니다. 

- **경기 단위 어트리뷰션**: 신규 결제의 65%가 특정 경기(결제 후 첫 시청 콘텐츠)에 귀속되며, 빅매치는 판매 견인력 3배
- **최초 vs 복귀**: 해지 유저의 일부가 재결제하는 복귀 패턴을 결제 이벤트 테이블(purchases)로 분리 모델링
- **권종 체계**: 자사 이용권 플랜과 제휴 채널 판매를 구분
- **시즌성**: 종목별 시즌(야구 3~10월 등)과 중계 편성 빈도를 경기 일정에 반영

*※ 본 프로젝트의 모든 수치·비율은 시뮬레이션을 위해 임의로 설정한 값으로, 실제 서비스의 지표와 무관합니다.*

## 대시보드

**[▶ Google Data Studio 대시보드 직접 보기](https://datastudio.google.com/reporting/a0a79d8b-9e03-4406-ba7a-11c402068e4f)** (*구 Looker Studio, 로그인 없이 열람 가능)

![dashboard](dashboard.png)

- **KPI 카드**: 총 신규 판매 · 최초 결제 · 복귀 결제 · 경기 유입 비중, 카드별 월별 추이선(스파크라인)
- **월별 신규 판매**: 최초 + 복귀 누적 막대로 복귀 결제 비중의 증가 흐름 확인
- **경기별 결제 유도 TOP 10**: 경기명 + 경기일 기준, 셀 내 막대로 판매량 비교
- **종목별 판매 비중**: 경기에 귀속된 신규 판매의 종목 구성

## 분석: 경기 특성별 신규 판매량 회귀분석

[`match_sales_regression.ipynb`](match_sales_regression.ipynb)

실무에서는 리그·빅매치 여부 같은 도메인 변수로 경기 중요도 기준을 직접 세워 CRM 발송 규모를 나눴습니다. 이 노트북은 같은 질문을 포아송 회귀로 다시 풀어, 각 변수가 판매에 주는 영향을 배수로 정량화하고 학습에 쓰지 않은 기간으로 예측력을 검증합니다.

- 빅매치는 다른 조건이 같을 때 판매 약 3배 (95% CI 2.8~3.2배)
- 테스트 기간 평균 절대 오차: 종목별 평균 규칙 4.3건 → 회귀 3.2건
- 한계 발견: 복귀 결제가 시간이 갈수록 늘어나는 추세를 반영하지 못해 후반 기간을 과소 예측 → 최초/복귀 분리 모델링이 다음 단계

*※ 가상 데이터라 데이터 생성 시 설정한 효과를 모델이 다시 찾는 구조이며, 목적은 방법론 검증입니다.*

## 실행 방법

```bash
pip install pandas numpy gspread statsmodels matplotlib jupyter

python generate_ott_data_v3.py   # 가상 데이터 생성 → portfolio.db
python build_daily_sales.py      # 가공 → daily_match_sales.csv
python upload_to_sheets.py       # Google Sheets 업로드 (서비스 계정 필요)
jupyter notebook match_sales_regression.ipynb   # 회귀분석 (portfolio.db 필요)
```

업로드 단계는 Google Cloud 서비스 계정 키(`credentials.json`)와 대상 시트에 대한 편집 권한 공유가 필요합니다. 키 파일은 보안상 저장소에 포함되어 있지 않습니다.

## 기술 스택

`Python` `pandas` `statsmodels` `SQLite` `gspread` `Google Sheets API` `Looker Studio`

## 만든 사람

구독 기반 스포츠 OTT 서비스에서 Growth 데이터 분석과 CRM 마케팅을 담당하고 있습니다.
이 프로젝트는 실무의 반복 리포팅 업무를 개인 환경에서 자동화 파이프라인으로 재구성한 학습 프로젝트입니다.

## 구현 범위

- 가상 데이터 생성부터 SQL 추출, 가공, Google Sheets 자동 업로드까지 이어지는 파이프라인
- Google Data Studio 대시보드 (KPI 스코어카드, 월별 누적 추이, 종목 비중, 경기별 TOP 10)
- 경기 특성별 판매 회귀분석 (포아송 회귀) 및 학습에 쓰지 않은 기간으로 예측 검증
