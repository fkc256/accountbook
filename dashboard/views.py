"""dashboard 앱 뷰 — 홈 화면 및 월별 수입·지출 요약 대시보드.

home_view       : 로그인 후 첫 화면 (Quick Action Hub)
dashboard_view  : 월별 수입·지출 상세 대시보드
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from django.utils.timezone import now

from transactions.models import Transaction


@login_required
def home_view(request):
    """홈 화면 (Quick Action Hub) — 메뉴 아이콘만 표시하는 심플 랜딩."""
    return render(request, "dashboard/home.html")


@login_required
def dashboard_view(request):
    """월별 대시보드 — 수입·지출 합계 및 카테고리별 지출 요약."""
    month_param = request.GET.get("month")

    if month_param:
        try:
            year, month = map(int, month_param.split("-"))
        except (ValueError, AttributeError):
            year, month = _default_month(request.user)
    else:
        year, month = _default_month(request.user)

    qs = Transaction.objects.filter(
        user=request.user,
        occurred_at__year=year,
        occurred_at__month=month,
    )

    total_income = qs.filter(tx_type="IN").aggregate(s=Sum("amount"))["s"] or 0
    total_expense = qs.filter(tx_type="OUT").aggregate(s=Sum("amount"))["s"] or 0
    net = total_income - total_expense

    category_summary = (
        qs.values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    max_cat_total = 0
    if category_summary:
        max_cat_total = max(item["total"] for item in category_summary)

    return render(request, "dashboard/dashboard.html", {
        "year": year,
        "month": month,
        "total_income": total_income,
        "total_expense": total_expense,
        "net": net,
        "category_summary": category_summary,
        "max_cat_total": max_cat_total,
        "month_param": month_param or f"{year}-{month:02d}",
    })


def _default_month(user):
    """가장 최근 거래가 있는 월을 기본값으로, 없으면 현재 월"""
    latest = (
        Transaction.objects.filter(user=user)
        .order_by("-occurred_at")
        .values_list("occurred_at", flat=True)
        .first()
    )
    if latest:
        return latest.year, latest.month
    today = now().date()
    return today.year, today.month
