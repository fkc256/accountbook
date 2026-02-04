"""accountbook 프로젝트 루트 URL 설정.

각 Django 앱의 URL 설정을 include() 로 위임한다.
- /admin/         → Django 관리자
- /accounts/      → 로그인·회원가입 (accounts 앱)
- /transactions/  → 계좌·거래·정기거래·영수증 CRUD (transactions 앱)
- /dashboard/     → 대시보드 (dashboard 앱)
- /inmoney/       → 재무 건강 분석·GPT 분석·목표 관리 (analysis 앱)
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from dashboard.views import home_view

urlpatterns = [
    path("", home_view, name="home"),                      # 루트(/) → 홈 화면
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("transactions/", include("transactions.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("inmoney/", include("analysis.urls")),
]

# 개발 모드에서만 미디어 파일(영수증 이미지 등)을 Django 가 직접 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
