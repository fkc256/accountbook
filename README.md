# AccountBook

계좌 기반 거래 내역 관리 시스템 (Django + PostgreSQL)

## 프로젝트 개요

로그인한 사용자가 여러 개의 계좌를 등록하고, 각 계좌에 대한 입출금 거래 내역을 기록/조회/수정/삭제하며, 영수증 파일 업로드와 대시보드에서 월별/카테고리별 요약을 확인할 수 있는 웹 서비스입니다.

### MVP 범위

- Django Template 서버 렌더링 (JavaScript 미사용)
- PostgreSQL 로컬 설치 기반 DB (Docker 미사용)
- 파일 업로드는 로컬 MEDIA 저장
- GitHub Actions CI로 테스트 자동 실행

## 주요 기능

- **사용자 인증**: 회원가입 / 로그인 / 로그아웃 (본인 데이터만 접근 가능)
- **계좌 관리**: 계좌 CRUD, 계좌번호 마스킹 출력, 계좌 비활성 처리
- **거래 내역 관리**: 입출금 거래 CRUD, 기간/계좌/카테고리/입출금 필터, 키워드 검색
- **잔액 자동 관리**: 거래 생성/수정/삭제 시 계좌 잔액 자동 반영, 잔액 부족 경고
- **영수증 첨부**: 거래에 이미지/PDF 파일 업로드/조회/삭제 (거래당 1개, 5MB 제한)
- **정기 거래**: 매월 반복되는 수입/지출 자동 등록 및 관리
- **대시보드**: 월별 총수입/총지출/순합계, 카테고리별 집계 (CSS 막대바 시각화)
- **InMoney 분석**: 12개 항목 재무 건강 분석 + AI(GPT) 종합 분석
- **관리자 페이지**: Django Admin을 통한 데이터 관리 (계좌번호 마스킹 적용)

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python 3.12, Django 6.0.1 |
| Database | PostgreSQL (개발 시 SQLite 자동 전환) |
| Frontend | Django Template + Bootstrap 5.3 (JS 미사용) |
| AI 분석 | OpenAI GPT-4o-mini |
| CI | GitHub Actions |

## ERD

```
User (Django 기본 auth.User)
 ├── Account (1:N)          계좌 — 은행/잔액/활성 여부
 │    ├── Transaction (1:N)  거래 — 입출금/금액/날짜/가맹점
 │    │    ├── Category (N:1)    카테고리 — 수입/지출/공통
 │    │    └── Attachment (1:1)  영수증 — 파일 첨부
 │    └── RecurringTransaction (1:N)  정기 거래 — 매월 자동 실행
 └── Goal (1:1)             재무 목표 — 저축/소비 한도
```

## 프로젝트 구조

```
AccountBook/
├── accountbook/        # 프로젝트 설정 (settings, urls)
├── accounts/           # 사용자 인증 (가입/로그인/로그아웃)
├── transactions/       # 계좌, 거래, 영수증, 정기거래 관리
│   └── management/commands/
│       ├── seed_categories.py      # 기본 카테고리 초기화
│       ├── process_recurring.py    # 정기 거래 자동 실행
│       └── generate_dummy_data.py  # 테스트용 더미 데이터 생성
├── dashboard/          # 월별 대시보드
├── analysis/           # InMoney 재무 분석 + AI 분석
├── templates/          # 공통 템플릿 (base.html)
├── static/css/         # 커스텀 CSS (딥퍼플/인디고 테마)
├── media/              # 업로드 파일 저장소 (영수증)
├── .github/workflows/  # GitHub Actions CI 설정
└── manage.py
```

## 실행 방법

### 1. 저장소 클론

```bash
git clone https://github.com/<username>/AccountBook.git
cd AccountBook
```

### 2. 가상환경 생성 및 활성화

```bash
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
```

### 3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 4. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 항목을 설정합니다.

```env
# 필수
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True

# AI 분석 기능 사용 시
OPENAI_API_KEY=your-openai-api-key

# PostgreSQL 사용 시 (미설정 시 SQLite 자동 사용)
DATABASE_URL=postgres
DB_NAME=accountbook
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
```

### 5. 데이터베이스 마이그레이션

```bash
python manage.py migrate
```

### 6. 초기 카테고리 데이터 생성

```bash
python manage.py seed_categories
```

### 7. 관리자 계정 생성

```bash
python manage.py createsuperuser
```

### 8. 서버 실행

```bash
python manage.py runserver
```

접속: http://127.0.0.1:8000/dashboard/

## URL 구조

| 경로 | 기능 |
|------|------|
| `/accounts/login/` | 로그인 |
| `/accounts/logout/` | 로그아웃 |
| `/accounts/signup/` | 회원가입 |
| `/transactions/accounts/` | 계좌 목록 |
| `/transactions/accounts/new/` | 계좌 생성 |
| `/transactions/accounts/<pk>/` | 계좌 상세 |
| `/transactions/accounts/<pk>/edit/` | 계좌 수정 |
| `/transactions/accounts/<pk>/delete/` | 계좌 삭제 |
| `/transactions/` | 거래 내역 목록 (필터/검색) |
| `/transactions/new/` | 거래 생성 |
| `/transactions/<pk>/` | 거래 상세 |
| `/transactions/<pk>/edit/` | 거래 수정 |
| `/transactions/<pk>/delete/` | 거래 삭제 |
| `/transactions/<pk>/attachment/upload/` | 영수증 업로드 |
| `/transactions/<pk>/attachment/delete/` | 영수증 삭제 |
| `/transactions/recurring/` | 정기 거래 목록 |
| `/transactions/recurring/new/` | 정기 거래 생성 |
| `/dashboard/` | 월별 대시보드 |
| `/inmoney/` | InMoney 재무 분석 |
| `/inmoney/goal/` | 재무 목표 설정 |
| `/inmoney/gpt-analysis/` | AI 종합 분석 (POST) |
| `/admin/` | 관리자 페이지 |

## 테스트

### 테스트 실행

```bash
python manage.py test
```

### 테스트 커버리지 (57개 테스트)

| 앱 | 테스트 클래스 | 테스트 수 | 주요 항목 |
|----|-------------|-----------|----------|
| accounts | AuthTest | 7 | 로그인/로그아웃/회원가입, 비로그인 접근 차단 |
| transactions | AccountCRUDTest | 7 | 계좌 CRUD, 타 유저 접근 차단, 마스킹 |
| transactions | TransactionCRUDTest | 6 | 거래 CRUD, 타 유저 접근 차단 |
| transactions | TransactionFilterTest | 4 | 기간/계좌/카테고리/키워드 필터 |
| transactions | RecurringTransactionTest | 6 | 정기 거래 CRUD, 자동 실행, 중복 방지 |
| transactions | BalanceAutoUpdateTest | 7 | 잔액 자동 계산, 부족 경고, 확인 후 저장 |
| dashboard | DashboardViewTest | 8 | 월별 집계, 카테고리 요약, 사용자 분리 |
| analysis | InMoneyViewTest | 6 | 재무 분석 데이터, 점수/등급, 사용자 분리 |
| analysis | GoalViewTest | 4 | 목표 생성/수정, 인증 |
| analysis | GptAnalysisViewTest | 2 | 인증, HTTP 메서드 제한 |

## 관리 명령어

| 명령어 | 설명 |
|--------|------|
| `python manage.py seed_categories` | 기본 카테고리 데이터 초기화 |
| `python manage.py process_recurring` | 정기 거래 자동 실행 (매일 cron 실행 권장) |
| `python manage.py generate_dummy_data` | 테스트용 6개월치 더미 데이터 생성 (fkc256 유저) |
| `python manage.py createsuperuser` | 관리자 계정 생성 |

## 보안

- **비밀번호**: Django 기본 해시 저장 (PBKDF2)
- **환경변수**: SECRET_KEY, DB 비밀번호, API 키 등 `.env` 파일로 분리
- **계좌번호**: 화면 및 관리자 페이지에서 마스킹 출력 (예: `110-****-9012`)
- **CSRF**: 모든 폼에 `{% csrf_token %}` 적용
- **접근 제어**: `@login_required` + QuerySet 필터로 본인 데이터만 접근
- **파일 업로드**: 확장자(jpg/png/gif/pdf) 및 크기(5MB) 제한
