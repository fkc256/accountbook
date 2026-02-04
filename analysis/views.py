"""analysis 앱 뷰 — InMoney 재무 건강 분석·GPT 분석·목표 관리.

inmoney_view()  : 12개 섹션의 재무 지표를 집계하여 InMoney 대시보드 렌더링
gpt_analysis_view() : 집계 데이터를 GPT-4o-mini 에 전달해 종합 진단서를 생성
goal_update_view()  : 목표 저축·소비 한도 설정/수정

점수 산정 기준 (50점 기본):
  - 저축률  > 20% → +15  |  > 10% → +10  |  > 0% → +5
  - 현금 체력 ≥ 6개월 → +15  |  ≥ 3 → +10  |  ≥ 1 → +5
  - 고정비 ≤ 30% → +10  |  ≤ 50% → +5
  - 위험 신호 0개 → +10  |  1개 → +5
"""

from statistics import stdev, mean

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.db.models.functions import TruncQuarter
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils.timezone import now
from django.views.decorators.http import require_POST
from openai import OpenAI

from transactions.models import Transaction, Account, RecurringTransaction, Goal
from .forms import GoalForm


def _monthly_data(qs, months=12):
    """최근 N개월 월별 수입/지출 집계를 반환한다.
    데이터가 전혀 없는 현재 월은 제외한다."""
    today = now().date()
    result = []
    for i in range(months - 1, -1, -1):
        y = today.year
        m = today.month - i
        while m <= 0:
            m += 12
            y -= 1
        month_qs = qs.filter(occurred_at__year=y, occurred_at__month=m)
        income = month_qs.filter(tx_type="IN").aggregate(s=Sum("amount"))["s"] or 0
        expense = month_qs.filter(tx_type="OUT").aggregate(s=Sum("amount"))["s"] or 0
        # 현재 월인데 데이터가 전혀 없으면 제외
        if y == today.year and m == today.month and income == 0 and expense == 0:
            continue
        result.append({
            "label": f"{y}-{m:02d}",
            "income": income,
            "expense": expense,
            "saving": income - expense,
        })
    return result


@login_required
def inmoney_view(request):
    """InMoney 재무 건강 분석 페이지.

    12개 섹션의 지표를 계산하여 CSS 차트용 데이터와 함께 템플릿에 전달한다.
    """
    user = request.user
    all_tx = Transaction.objects.filter(user=user)
    today = now().date()

    # ── 기본 집계 ──
    total_income = all_tx.filter(tx_type="IN").aggregate(s=Sum("amount"))["s"] or 0
    total_expense = all_tx.filter(tx_type="OUT").aggregate(s=Sum("amount"))["s"] or 0
    net = total_income - total_expense
    spending_rate = (total_expense / total_income * 100) if total_income > 0 else 0

    # ── 1. 수입·지출 구조 ──
    recurring_total = RecurringTransaction.objects.filter(
        user=user, is_active=True, tx_type="OUT"
    ).aggregate(s=Sum("amount"))["s"] or 0

    fixed_ratio = (recurring_total / total_expense * 100) if total_expense > 0 else 0
    variable_ratio = 100 - fixed_ratio if total_expense > 0 else 0

    # ── 2. 저축·잔여 자금 ──
    monthly = _monthly_data(all_tx)
    saving_rate = (net / total_income * 100) if total_income > 0 else 0
    savings_list = [m["saving"] for m in monthly]
    saving_volatility = stdev(savings_list) if len(savings_list) >= 2 else 0

    # ── 3. 현금 체력 ──
    total_assets = Account.objects.filter(user=user, is_active=True).aggregate(
        s=Sum("balance")
    )["s"] or 0

    expense_months = [m["expense"] for m in monthly if m["expense"] > 0]
    avg_monthly_expense = mean(expense_months) if expense_months else 0
    cash_endurance_months = (
        total_assets / avg_monthly_expense if avg_monthly_expense > 0 else 0
    )

    # ── 4. 소비 패턴·리듬 ──
    monthly_expenses = [m["expense"] for m in monthly]
    expense_volatility = stdev(monthly_expenses) if len(monthly_expenses) >= 2 else 0

    early_expense = all_tx.filter(
        tx_type="OUT", occurred_at__day__lte=15
    ).aggregate(s=Sum("amount"))["s"] or 0
    late_expense = all_tx.filter(
        tx_type="OUT", occurred_at__day__gt=15
    ).aggregate(s=Sum("amount"))["s"] or 0
    total_for_split = early_expense + late_expense
    early_ratio = (early_expense / total_for_split * 100) if total_for_split > 0 else 50
    late_ratio = (late_expense / total_for_split * 100) if total_for_split > 0 else 50

    # ── 5. 카테고리 소비 ──
    category_data = (
        all_tx.filter(tx_type="OUT", category__isnull=False)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    category_labels = [c["category__name"] for c in category_data]
    category_values = [c["total"] for c in category_data]
    top_categories = list(category_data[:5])

    # ── 6. 만족 소비 ──
    satisfaction_expense = all_tx.filter(
        tx_type="OUT", category__is_satisfaction=True
    ).aggregate(s=Sum("amount"))["s"] or 0
    satisfaction_ratio = (
        satisfaction_expense / total_expense * 100 if total_expense > 0 else 0
    )

    satisfaction_monthly = []
    for m in monthly:
        y, mo = map(int, m["label"].split("-"))
        sat_amt = all_tx.filter(
            tx_type="OUT",
            category__is_satisfaction=True,
            occurred_at__year=y,
            occurred_at__month=mo,
        ).aggregate(s=Sum("amount"))["s"] or 0
        satisfaction_monthly.append({"label": m["label"], "amount": sat_amt})

    # ── 7. 안정성·위험 신호 ──
    warnings = []
    neg_balance_accounts = Account.objects.filter(user=user, balance__lte=0).count()
    if neg_balance_accounts > 0:
        warnings.append("계좌 잔액이 0 이하인 계좌가 있습니다.")

    consecutive_deficit = 0
    max_consecutive_deficit = 0
    for m in monthly:
        if m["saving"] < 0:
            consecutive_deficit += 1
            max_consecutive_deficit = max(max_consecutive_deficit, consecutive_deficit)
        else:
            consecutive_deficit = 0
    if max_consecutive_deficit >= 2:
        warnings.append(f"연속 {max_consecutive_deficit}개월 적자가 발생했습니다.")

    if fixed_ratio > 50:
        warnings.append(f"고정비 비중이 {fixed_ratio:.0f}%로 높습니다.")

    recent_savings = savings_list[-3:] if len(savings_list) >= 3 else savings_list
    if recent_savings and all(s <= 0 for s in recent_savings):
        warnings.append("최근 저축이 중단되었습니다.")

    # ── 8. 계좌 관리 ──
    account_balances = list(
        Account.objects.filter(user=user, is_active=True).values("name", "balance")
    )

    account_expense_data = list(
        all_tx.filter(tx_type="OUT")
        .values("account__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    account_income_data = list(
        all_tx.filter(tx_type="IN")
        .values("account__name")
        .annotate(count=Count("id"))
    )
    account_freq = {}
    for item in account_expense_data:
        name = item["account__name"]
        account_freq[name] = account_freq.get(name, 0) + item["count"]
    for item in account_income_data:
        name = item["account__name"]
        account_freq[name] = account_freq.get(name, 0) + item["count"]

    # ── 9. 습관·행동 ──
    repeat_spending = list(
        all_tx.filter(tx_type="OUT")
        .exclude(merchant="")
        .values("merchant", "amount")
        .annotate(count=Count("id"))
        .filter(count__gte=3)
        .order_by("-count")
    )

    avg_expense_amount = 0
    expense_tx = all_tx.filter(tx_type="OUT")
    expense_count = expense_tx.count()
    if expense_count > 0:
        avg_expense_amount = (expense_tx.aggregate(s=Sum("amount"))["s"] or 0) / expense_count

    small_threshold = avg_expense_amount * 0.2 if avg_expense_amount > 0 else 0
    small_spending_total = 0
    small_spending_count = 0
    if small_threshold > 0:
        small_qs = expense_tx.filter(amount__lte=small_threshold)
        small_spending_total = small_qs.aggregate(s=Sum("amount"))["s"] or 0
        small_spending_count = small_qs.count()

    impulse_count = expense_tx.filter(memo="", merchant="").count()
    impulse_ratio = (impulse_count / expense_count * 100) if expense_count > 0 else 0

    small_monthly = []
    for m in monthly:
        y, mo = map(int, m["label"].split("-"))
        if small_threshold > 0:
            amt = all_tx.filter(
                tx_type="OUT",
                amount__lte=small_threshold,
                occurred_at__year=y,
                occurred_at__month=mo,
            ).aggregate(s=Sum("amount"))["s"] or 0
        else:
            amt = 0
        small_monthly.append({"label": m["label"], "amount": amt})

    # ── 10. 시간 기반 ──
    quarterly_data = (
        all_tx.filter(tx_type="OUT")
        .annotate(quarter=TruncQuarter("occurred_at"))
        .values("quarter")
        .annotate(total=Sum("amount"))
        .order_by("quarter")
    )
    quarter_labels = []
    quarter_values = []
    for q in quarterly_data:
        qd = q["quarter"]
        quarter_num = (qd.month - 1) // 3 + 1
        quarter_labels.append(f"{qd.year}년 {quarter_num}분기")
        quarter_values.append(q["total"])

    recent_months = monthly[-3:]
    change_rates = []
    for i in range(1, len(recent_months)):
        prev = recent_months[i - 1]["expense"]
        curr = recent_months[i]["expense"]
        rate = round((curr - prev) / prev * 100, 1) if prev > 0 else 0
        change_rates.append({
            "label": f"{recent_months[i-1]['label']} → {recent_months[i]['label']}",
            "rate": rate,
        })

    # ── 11. 목표 관리 ──
    goal = Goal.objects.filter(user=user).first()
    saving_achievement = 0
    spending_usage = 0
    if goal:
        if goal.target_saving > 0:
            saving_achievement = min(net / goal.target_saving * 100, 100) if net > 0 else 0
        current_month_expense = all_tx.filter(
            tx_type="OUT",
            occurred_at__year=today.year,
            occurred_at__month=today.month,
        ).aggregate(s=Sum("amount"))["s"] or 0
        if goal.monthly_spending_limit > 0:
            spending_usage = current_month_expense / goal.monthly_spending_limit * 100

    # ── 12. 종합 지표 ──
    hhi = 0
    if category_values and total_expense > 0:
        shares = [(v / total_expense) ** 2 for v in category_values]
        hhi = sum(shares) * 10000

    score = 50
    if saving_rate > 20:
        score += 15
    elif saving_rate > 10:
        score += 10
    elif saving_rate > 0:
        score += 5

    if cash_endurance_months >= 6:
        score += 15
    elif cash_endurance_months >= 3:
        score += 10
    elif cash_endurance_months >= 1:
        score += 5

    if fixed_ratio <= 30:
        score += 10
    elif fixed_ratio <= 50:
        score += 5

    if len(warnings) == 0:
        score += 10
    elif len(warnings) <= 1:
        score += 5

    score = max(0, min(100, score))
    balance_index = saving_rate - spending_rate if total_income > 0 else 0

    # ── CSS 차트용 데이터 가공 ──
    # 카테고리 파이 차트: 누적 퍼센트 계산
    cat_total = sum(category_values) if category_values else 1
    category_pie_data = []
    cumulative = 0
    colors = ["#4a90d9", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6",
              "#1abc9c", "#e67e22", "#3498db", "#e91e63", "#00bcd4"]
    for i, (label, value) in enumerate(zip(category_labels, category_values)):
        pct = round(value / cat_total * 100, 1) if cat_total > 0 else 0
        category_pie_data.append({
            "label": label,
            "value": value,
            "pct": pct,
            "start": round(cumulative, 1),
            "end": round(cumulative + pct, 1),
            "color": colors[i % len(colors)],
        })
        cumulative += pct

    # top_categories에 max값 추가
    top_cat_values = [c["total"] for c in top_categories]
    max_top_category = max(top_cat_values) if top_cat_values else 1

    # monthly 리스트: saving_abs 추가 + short_label
    for m in monthly:
        m["saving_abs"] = abs(m["saving"])
        m["mm"] = m["label"].split("-")[1]

    max_monthly_income = max((m["income"] for m in monthly), default=1) or 1
    max_monthly_expense = max((m["expense"] for m in monthly), default=1) or 1
    max_monthly_saving_abs = max((m["saving_abs"] for m in monthly), default=1) or 1

    # satisfaction_monthly: short_label
    for m in satisfaction_monthly:
        m["mm"] = m["label"].split("-")[1]
    max_satisfaction = max((m["amount"] for m in satisfaction_monthly), default=1) or 1

    # small_monthly: short_label
    for m in small_monthly:
        m["mm"] = m["label"].split("-")[1]
    max_small = max((m["amount"] for m in small_monthly), default=1) or 1

    # account_balances max값
    max_account_balance = max((a["balance"] for a in account_balances), default=1) or 1

    # account_expense_data max값
    max_account_expense = max((a["total"] for a in account_expense_data), default=1) or 1

    # quarterly max값
    quarterly_data_list = [
        {"label": quarter_labels[i], "value": quarter_values[i]}
        for i in range(len(quarter_labels))
    ]
    max_quarterly = max(quarter_values) if quarter_values else 1

    # monthly compare: max of income and expense
    max_monthly_compare = max(max_monthly_income, max_monthly_expense)

    # income vs expense bar max
    max_income_expense = max(total_income, total_expense) or 1

    # 종합 등급
    if score >= 90:
        grade = "S"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    # 점수 색상
    if score >= 70:
        score_color = "#2e7d32"
    elif score >= 40:
        score_color = "#f57f17"
    else:
        score_color = "#c62828"

    context = {
        # 1. 수입·지출
        "total_income": total_income,
        "total_expense": total_expense,
        "net": net,
        "spending_rate": round(spending_rate, 1),
        "remaining_rate": round(100 - spending_rate, 1),
        "fixed_ratio": round(fixed_ratio, 1),
        "variable_ratio": round(variable_ratio, 1),
        "max_income_expense": max_income_expense,
        # 2. 저축
        "saving_rate": round(saving_rate, 1),
        "saving_volatility": round(saving_volatility),
        "monthly": monthly,
        "max_monthly_saving_abs": max_monthly_saving_abs,
        # 3. 현금 체력
        "total_assets": total_assets,
        "avg_monthly_expense": round(avg_monthly_expense),
        "cash_endurance_months": round(cash_endurance_months, 1),
        # 4. 소비 패턴
        "expense_volatility": round(expense_volatility),
        "early_ratio": round(early_ratio, 1),
        "late_ratio": round(late_ratio, 1),
        "max_monthly_expense": max_monthly_expense,
        # 5. 카테고리
        "category_pie_data": category_pie_data,
        "top_categories": top_categories,
        "max_top_category": max_top_category,
        # 6. 만족 소비
        "satisfaction_ratio": round(satisfaction_ratio, 1),
        "satisfaction_remaining": round(100 - satisfaction_ratio, 1),
        "satisfaction_expense": satisfaction_expense,
        "satisfaction_monthly": satisfaction_monthly,
        "max_satisfaction": max_satisfaction,
        # 7. 위험 신호
        "warnings": warnings,
        # 8. 계좌
        "account_balances": account_balances,
        "max_account_balance": max_account_balance,
        "account_expense_data": account_expense_data,
        "max_account_expense": max_account_expense,
        "account_freq": account_freq,
        # 9. 습관
        "repeat_spending": repeat_spending,
        "small_spending_total": small_spending_total,
        "small_spending_count": small_spending_count,
        "impulse_ratio": round(impulse_ratio, 1),
        "small_monthly": small_monthly,
        "max_small": max_small,
        # 10. 시간
        "quarterly_data_list": quarterly_data_list,
        "max_quarterly": max_quarterly,
        "max_monthly_compare": max_monthly_compare,
        "change_rates": change_rates,
        # 11. 목표
        "goal": goal,
        "saving_achievement": round(saving_achievement, 1),
        "spending_usage": round(spending_usage, 1),
        # 12. 종합
        "today": today,
        "hhi": round(hhi),
        "financial_score": score,
        "grade": grade,
        "score_color": score_color,
        "balance_index": round(balance_index, 1),
    }

    return render(request, "analysis/inmoney.html", context)


@login_required
@require_POST
def gpt_analysis_view(request):
    """InMoney 데이터를 GPT에게 보내 종합 분석 및 조언을 받는다."""
    user = request.user
    all_tx = Transaction.objects.filter(user=user)
    today = now().date()

    # ── 핵심 데이터 수집 ──
    total_income = all_tx.filter(tx_type="IN").aggregate(s=Sum("amount"))["s"] or 0
    total_expense = all_tx.filter(tx_type="OUT").aggregate(s=Sum("amount"))["s"] or 0
    net = total_income - total_expense
    spending_rate = (total_expense / total_income * 100) if total_income > 0 else 0

    recurring_out_total = RecurringTransaction.objects.filter(
        user=user, is_active=True, tx_type="OUT"
    ).aggregate(s=Sum("amount"))["s"] or 0
    fixed_ratio = (recurring_out_total / total_expense * 100) if total_expense > 0 else 0

    # ── 정기 거래 상세 수집 ──
    recurring_income_qs = RecurringTransaction.objects.filter(
        user=user, is_active=True, tx_type="IN"
    )
    recurring_expense_qs = RecurringTransaction.objects.filter(
        user=user, is_active=True, tx_type="OUT"
    )
    recurring_in_total = recurring_income_qs.aggregate(s=Sum("amount"))["s"] or 0
    recurring_income_list = list(recurring_income_qs.values(
        "merchant", "memo", "amount", "recurring_day", "category__name"
    ))
    recurring_expense_list = list(recurring_expense_qs.values(
        "merchant", "memo", "amount", "recurring_day", "category__name"
    ))

    monthly = _monthly_data(all_tx)
    saving_rate = (net / total_income * 100) if total_income > 0 else 0
    savings_list = [m["saving"] for m in monthly]
    saving_volatility = stdev(savings_list) if len(savings_list) >= 2 else 0

    total_assets = Account.objects.filter(user=user, is_active=True).aggregate(
        s=Sum("balance")
    )["s"] or 0
    expense_months = [m["expense"] for m in monthly if m["expense"] > 0]
    avg_monthly_expense = mean(expense_months) if expense_months else 0
    cash_endurance_months = (
        total_assets / avg_monthly_expense if avg_monthly_expense > 0 else 0
    )

    monthly_expenses = [m["expense"] for m in monthly]
    expense_volatility = stdev(monthly_expenses) if len(monthly_expenses) >= 2 else 0

    early_expense = all_tx.filter(
        tx_type="OUT", occurred_at__day__lte=15
    ).aggregate(s=Sum("amount"))["s"] or 0
    late_expense = all_tx.filter(
        tx_type="OUT", occurred_at__day__gt=15
    ).aggregate(s=Sum("amount"))["s"] or 0
    total_for_split = early_expense + late_expense
    early_ratio = (early_expense / total_for_split * 100) if total_for_split > 0 else 50
    late_ratio = 100 - early_ratio

    category_data = list(
        all_tx.filter(tx_type="OUT", category__isnull=False)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")[:10]
    )

    satisfaction_expense = all_tx.filter(
        tx_type="OUT", category__is_satisfaction=True
    ).aggregate(s=Sum("amount"))["s"] or 0
    satisfaction_ratio = (
        satisfaction_expense / total_expense * 100 if total_expense > 0 else 0
    )

    # 위험 신호
    warnings = []
    neg_balance_accounts = Account.objects.filter(user=user, balance__lte=0).count()
    if neg_balance_accounts > 0:
        warnings.append("계좌 잔액이 0 이하인 계좌 존재")
    consecutive_deficit = 0
    max_consecutive_deficit = 0
    for m in monthly:
        if m["saving"] < 0:
            consecutive_deficit += 1
            max_consecutive_deficit = max(max_consecutive_deficit, consecutive_deficit)
        else:
            consecutive_deficit = 0
    if max_consecutive_deficit >= 2:
        warnings.append(f"연속 {max_consecutive_deficit}개월 적자")
    if fixed_ratio > 50:
        warnings.append(f"고정비 비중 {fixed_ratio:.0f}%로 높음")

    # 습관 지표
    expense_tx = all_tx.filter(tx_type="OUT")
    expense_count = expense_tx.count()
    impulse_count = expense_tx.filter(memo="", merchant="").count()
    impulse_ratio = (impulse_count / expense_count * 100) if expense_count > 0 else 0

    # 종합 지표
    category_values = [c["total"] for c in category_data]
    hhi = 0
    if category_values and total_expense > 0:
        shares = [(v / total_expense) ** 2 for v in category_values]
        hhi = sum(shares) * 10000

    score = 50
    if saving_rate > 20:
        score += 15
    elif saving_rate > 10:
        score += 10
    elif saving_rate > 0:
        score += 5
    if cash_endurance_months >= 6:
        score += 15
    elif cash_endurance_months >= 3:
        score += 10
    elif cash_endurance_months >= 1:
        score += 5
    if fixed_ratio <= 30:
        score += 10
    elif fixed_ratio <= 50:
        score += 5
    if len(warnings) == 0:
        score += 10
    elif len(warnings) <= 1:
        score += 5
    score = max(0, min(100, score))
    balance_index = saving_rate - spending_rate if total_income > 0 else 0

    # 목표
    goal = Goal.objects.filter(user=user).first()
    goal_info = ""
    if goal:
        saving_achievement = min(net / goal.target_saving * 100, 100) if goal.target_saving > 0 and net > 0 else 0
        current_month_expense = all_tx.filter(
            tx_type="OUT",
            occurred_at__year=today.year,
            occurred_at__month=today.month,
        ).aggregate(s=Sum("amount"))["s"] or 0
        spending_usage = (current_month_expense / goal.monthly_spending_limit * 100) if goal.monthly_spending_limit > 0 else 0
        goal_info = (
            f"- 목표 저축 금액: {goal.target_saving:,}원, 달성률: {saving_achievement:.1f}%\n"
            f"- 월 목표 소비 금액: {goal.monthly_spending_limit:,}원, 이번달 사용률: {spending_usage:.1f}%"
        )

    # ── 정기 거래 텍스트 생성 ──
    def _recurring_label(item):
        name = item["merchant"] or item["memo"] or item["category__name"] or "미지정"
        return f"  - {name}: 매월 {item['recurring_day']}일, {item['amount']:,}원"

    recurring_in_text = chr(10).join(_recurring_label(r) for r in recurring_income_list) if recurring_income_list else "  - 없음"
    recurring_out_text = chr(10).join(_recurring_label(r) for r in recurring_expense_list) if recurring_expense_list else "  - 없음"

    # ── GPT에게 보낼 데이터 요약 ──
    data_summary = f"""[사용자 재무 데이터 - InMoney 분석]

1. 수입·지출 구조
- 총 수입: {total_income:,}원
- 총 지출: {total_expense:,}원
- 잔여 금액: {net:,}원
- 소비율: {spending_rate:.1f}%
- 고정비 비중: {fixed_ratio:.1f}%
- 변동비 비중: {100 - fixed_ratio:.1f}%

2. 정기 거래 (매월 반복되는 고정 수입/지출)
[정기 수입] 월 합계: {recurring_in_total:,}원 (예: 월급, 정기 이자 등)
{recurring_in_text}
[정기 지출] 월 합계: {recurring_out_total:,}원 (예: 대출이자, 월세, 구독료 등)
{recurring_out_text}
- 정기 지출이 총 지출에서 차지하는 비중(고정비율): {fixed_ratio:.1f}%
- 정기 수입 대비 정기 지출 비율: {(recurring_out_total / recurring_in_total * 100) if recurring_in_total > 0 else 0:.1f}%
- 정기 수입 후 남는 가용 소득(정기수입-정기지출): {recurring_in_total - recurring_out_total:,}원

3. 저축·잔여 자금
- 저축률: {saving_rate:.1f}%
- 저축 변동성(표준편차): {round(saving_volatility):,}원

4. 현금 체력 (유동성)
- 금융자산 합계: {total_assets:,}원
- 월 평균 지출: {round(avg_monthly_expense):,}원
- 버틸 수 있는 개월 수: {cash_endurance_months:.1f}개월

5. 소비 패턴
- 소비 변동성(표준편차): {round(expense_volatility):,}원
- 월초(1~15일) 비중: {early_ratio:.1f}%
- 월말(16일~) 비중: {late_ratio:.1f}%

6. 카테고리별 소비 (상위)
{chr(10).join(f"- {c['category__name']}: {c['total']:,}원" for c in category_data)}

7. 만족 소비
- 만족 소비 금액: {satisfaction_expense:,}원
- 만족 소비 비율: {satisfaction_ratio:.1f}%

8. 위험 신호
{chr(10).join(f"- {w}" for w in warnings) if warnings else "- 없음"}

9. 습관·행동 지표
- 충동 소비 비율: {impulse_ratio:.1f}%

10. 월별 추이 (최근 12개월)
{chr(10).join(f"- {m['label']}: 수입 {m['income']:,}원 / 지출 {m['expense']:,}원 / 저축 {m['saving']:,}원" for m in monthly)}

11. 종합 지표
- 소비 집중도(HHI): {round(hhi)}
- 재무 안정성 점수: {score}/100
- 소비-저축 밸런스: {round(balance_index, 1)}

12. 목표 관리
{goal_info if goal_info else "- 목표 미설정"}
"""

    # ── GPT API 호출 ──
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "당신은 전문 재무 분석가입니다. 인바디(InBody)가 체성분을 분석하듯, "
                        "사용자의 재무 데이터를 종합 분석하여 '재무 건강 진단서'를 작성해주세요.\n\n"
                        "특히 '정기 거래' 데이터를 주의 깊게 분석하세요:\n"
                        "- 정기 수입(월급, 이자 등)은 매달 안정적으로 들어오는 소득입니다.\n"
                        "- 정기 지출(대출이자, 월세, 구독료, 보험료 등)은 매달 빠져나가는 고정 비용입니다.\n"
                        "- 정기 수입 대비 정기 지출 비율이 높으면 가용 소득이 줄어들어 재무 유연성이 떨어집니다.\n"
                        "- 구독료(넷플릭스, 유튜브 프리미엄 등)가 과도하지 않은지도 확인하세요.\n"
                        "- 정기 수입에서 정기 지출을 뺀 '가용 소득'이 변동 지출을 감당할 수 있는지 판단하세요.\n\n"
                        "다음 형식으로 분석해주세요:\n"
                        "1. 재무 건강 종합 등급 (S/A/B/C/D/F 등급과 한 줄 요약)\n"
                        "2. 강점 분석 (잘하고 있는 부분 2~3가지)\n"
                        "3. 약점 분석 (개선이 필요한 부분 2~3가지)\n"
                        "4. 정기 거래 진단 (고정 수입/지출 구조 분석, 구독 서비스 효율성, 가용 소득 평가)\n"
                        "5. 위험 신호 진단 (주의해야 할 사항)\n"
                        "6. 맞춤 실행 조언 (구체적이고 실천 가능한 3~5가지 조언, 정기 거래 최적화 포함)\n"
                        "7. 한 줄 총평\n\n"
                        "한국어로 답변하고, 숫자는 천 단위 쉼표를 사용해주세요. "
                        "분석은 구체적이고 데이터 기반으로 해주세요."
                    ),
                },
                {
                    "role": "user",
                    "content": data_summary,
                },
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        analysis_text = response.choices[0].message.content
        return JsonResponse({"status": "ok", "analysis": analysis_text})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)


@login_required
def goal_update_view(request):
    """재무 목표 설정·수정. Goal 이 없으면 자동 생성(get_or_create)."""
    goal, created = Goal.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = GoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            return redirect("inmoney")
    else:
        form = GoalForm(instance=goal)
    return render(request, "analysis/goal_form.html", {"form": form})
