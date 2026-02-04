"""transactions 앱 뷰 — 계좌·거래·영수증·정기거래 CRUD.

잔액 관리 정책:
  - 거래 생성 시 _apply_balance() 로 계좌 잔액을 원자적으로 갱신
  - 거래 수정 시 기존 거래를 _reverse_balance() 로 되돌린 뒤 새 거래를 적용
  - 거래 삭제 시 _reverse_balance() 로 잔액 복구
  - 출금 시 잔액 부족이면 경고를 표시하되, 사용자가 confirm 하면 음수 잔액 허용
"""

from django.contrib.auth.decorators import login_required
from django.db.models import F, Q
from django.shortcuts import render, redirect, get_object_or_404
from .models import Account, Transaction, Attachment, RecurringTransaction
from .forms import AccountForm, TransactionForm, AttachmentForm, RecurringTransactionForm


# ──────────────────────────────────
# 잔액 계산 헬퍼
# ──────────────────────────────────

def _apply_balance(account_id, tx_type, amount):
    """거래 적용: 입금이면 +, 출금이면 -"""
    if tx_type == "IN":
        Account.objects.filter(pk=account_id).update(balance=F("balance") + amount)
    else:
        Account.objects.filter(pk=account_id).update(balance=F("balance") - amount)


def _reverse_balance(account_id, tx_type, amount):
    """거래 되돌림: 입금이었으면 -, 출금이었으면 +"""
    if tx_type == "IN":
        Account.objects.filter(pk=account_id).update(balance=F("balance") - amount)
    else:
        Account.objects.filter(pk=account_id).update(balance=F("balance") + amount)


# ──────────────────────────────────
# Account CRUD
# ──────────────────────────────────

@login_required
def account_list(request):
    """로그인 유저의 전체 계좌 목록."""
    accounts = Account.objects.filter(user=request.user)
    return render(request, "transactions/account_list.html", {"accounts": accounts})


@login_required
def account_detail(request, pk):
    """계좌 상세 — 해당 계좌의 거래 내역을 최신순으로 표시."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    transactions = (
        Transaction.objects.filter(account=account, user=request.user)
        .select_related("category")
        .order_by("-occurred_at", "-pk")
    )
    return render(request, "transactions/account_detail.html", {
        "account": account,
        "transactions": transactions,
    })


@login_required
def account_create(request):
    """새 계좌 등록. user 필드는 서버에서 자동 할당."""
    if request.method == "POST":
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            return redirect("account_list")
    else:
        form = AccountForm()
    return render(request, "transactions/account_form.html", {"form": form})


@login_required
def account_update(request, pk):
    """계좌 정보 수정."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == "POST":
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            return redirect("account_detail", pk=account.pk)
    else:
        form = AccountForm(instance=account)
    return render(request, "transactions/account_form.html", {"form": form})


@login_required
def account_delete(request, pk):
    """계좌 삭제 확인 → POST 시 삭제 (CASCADE 로 하위 거래도 함께 삭제)."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == "POST":
        account.delete()
        return redirect("account_list")
    return render(request, "transactions/account_confirm_delete.html", {"account": account})


# ──────────────────────────────────
# Transaction CRUD + 필터/검색
# ──────────────────────────────────

@login_required
def transaction_list(request):
    """거래 내역 목록. 계좌·카테고리·입출금·기간·키워드 필터를 지원."""
    qs = Transaction.objects.filter(user=request.user).select_related("account", "category")

    # 계좌 필터
    account_id = request.GET.get("account")
    if account_id:
        qs = qs.filter(account_id=account_id)

    # 카테고리 필터
    category_id = request.GET.get("category")
    if category_id:
        qs = qs.filter(category_id=category_id)

    # 입출금 필터
    tx_type = request.GET.get("tx_type")
    if tx_type in ("IN", "OUT"):
        qs = qs.filter(tx_type=tx_type)

    # 기간 필터
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")
    if date_from:
        qs = qs.filter(occurred_at__gte=date_from)
    if date_to:
        qs = qs.filter(occurred_at__lte=date_to)

    # 키워드 검색 (메모 + 가맹점)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(memo__icontains=q) | Q(merchant__icontains=q))

    accounts = Account.objects.filter(user=request.user, is_active=True)

    from .models import Category
    categories = Category.objects.all()

    return render(request, "transactions/transaction_list.html", {
        "transactions": qs,
        "accounts": accounts,
        "categories": categories,
        "params": request.GET,
    })


@login_required
def transaction_detail(request, pk):
    """거래 상세 — 첨부 영수증이 있으면 함께 표시."""
    tx = get_object_or_404(
        Transaction.objects.select_related("account", "category"),
        pk=pk, user=request.user,
    )
    attachment = getattr(tx, "attachment", None)
    return render(request, "transactions/transaction_detail.html", {
        "tx": tx,
        "attachment": attachment,
    })


@login_required
def transaction_create(request):
    """새 거래 등록. 출금 시 잔액 부족 경고 → confirm 시 음수 잔액 허용."""
    balance_warning = None
    if request.method == "POST":
        form = TransactionForm(request.POST, user=request.user)
        if form.is_valid():
            tx = form.save(commit=False)
            tx.user = request.user

            # 잔액 부족 경고 (출금 시)
            account = tx.account
            if tx.tx_type == "OUT" and account.balance < tx.amount:
                balance_warning = (
                    f"잔액이 부족합니다. "
                    f"현재 잔액: {account.balance:,}원, 출금 금액: {tx.amount:,}원"
                )
                # 경고만 표시하고 저장은 허용 (음수 잔액 허용)
                if "confirm" not in request.POST:
                    return render(request, "transactions/transaction_form.html", {
                        "form": form,
                        "balance_warning": balance_warning,
                    })

            # 잔액 업데이트
            _apply_balance(account.pk, tx.tx_type, tx.amount)
            account.refresh_from_db()
            tx.balance_after = account.balance
            tx.save()
            return redirect("transaction_list")
    else:
        form = TransactionForm(user=request.user)
    return render(request, "transactions/transaction_form.html", {
        "form": form,
        "balance_warning": balance_warning,
    })


@login_required
def transaction_update(request, pk):
    """거래 수정. ① 기존 거래 잔액 되돌림 → ② 잔액 부족 검사 → ③ 새 거래 적용."""
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    old_account_id = tx.account_id
    old_tx_type = tx.tx_type
    old_amount = tx.amount

    balance_warning = None
    if request.method == "POST":
        form = TransactionForm(request.POST, instance=tx, user=request.user)
        if form.is_valid():
            new_tx = form.save(commit=False)

            # 1) 기존 거래 되돌림
            _reverse_balance(old_account_id, old_tx_type, old_amount)

            # 2) 잔액 부족 경고 (출금 시)
            Account.objects.get(pk=old_account_id)  # refresh
            new_account = Account.objects.get(pk=new_tx.account_id)
            if new_tx.tx_type == "OUT" and new_account.balance < new_tx.amount:
                balance_warning = (
                    f"잔액이 부족합니다. "
                    f"현재 잔액: {new_account.balance:,}원, 출금 금액: {new_tx.amount:,}원"
                )
                if "confirm" not in request.POST:
                    # 되돌림을 다시 원복
                    _apply_balance(old_account_id, old_tx_type, old_amount)
                    return render(request, "transactions/transaction_form.html", {
                        "form": form,
                        "balance_warning": balance_warning,
                    })

            # 3) 새 거래 적용
            _apply_balance(new_tx.account_id, new_tx.tx_type, new_tx.amount)
            new_account.refresh_from_db()
            new_tx.balance_after = new_account.balance
            new_tx.save()
            return redirect("transaction_detail", pk=tx.pk)
    else:
        form = TransactionForm(instance=tx, user=request.user)
    return render(request, "transactions/transaction_form.html", {
        "form": form,
        "balance_warning": balance_warning,
    })


@login_required
def transaction_delete(request, pk):
    """거래 삭제 확인 → POST 시 잔액 복구 후 삭제."""
    tx = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == "POST":
        # 잔액 되돌림
        _reverse_balance(tx.account_id, tx.tx_type, tx.amount)
        tx.delete()
        return redirect("transaction_list")
    return render(request, "transactions/transaction_confirm_delete.html", {"tx": tx})


# ──────────────────────────────────
# Attachment (영수증)
# ──────────────────────────────────

@login_required
def attachment_upload(request, tx_pk):
    """영수증 업로드. 이미 첨부파일이 있으면 상세 페이지로 리다이렉트."""
    tx = get_object_or_404(Transaction, pk=tx_pk, user=request.user)
    if hasattr(tx, "attachment"):
        return redirect("transaction_detail", pk=tx.pk)

    if request.method == "POST":
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            att = form.save(commit=False)
            att.user = request.user
            att.transaction = tx
            att.original_name = request.FILES["file"].name
            att.save()
            return redirect("transaction_detail", pk=tx.pk)
    else:
        form = AttachmentForm()
    return render(request, "transactions/attachment_form.html", {"form": form, "tx": tx})


@login_required
def attachment_delete(request, tx_pk):
    """영수증 삭제. 스토리지의 실제 파일도 함께 삭제."""
    tx = get_object_or_404(Transaction, pk=tx_pk, user=request.user)
    attachment = get_object_or_404(Attachment, transaction=tx, user=request.user)
    if request.method == "POST":
        attachment.file.delete(save=False)
        attachment.delete()
        return redirect("transaction_detail", pk=tx.pk)
    return render(request, "transactions/attachment_confirm_delete.html", {
        "tx": tx,
        "attachment": attachment,
    })


# ──────────────────────────────────
# RecurringTransaction (정기 거래)
# ──────────────────────────────────

@login_required
def recurring_list(request):
    """정기 거래 목록."""
    items = RecurringTransaction.objects.filter(user=request.user).select_related(
        "account", "category"
    )
    return render(request, "transactions/recurring_list.html", {"items": items})


@login_required
def recurring_create(request):
    """새 정기 거래 등록."""
    if request.method == "POST":
        form = RecurringTransactionForm(request.POST, user=request.user)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user
            obj.save()
            return redirect("recurring_list")
    else:
        form = RecurringTransactionForm(user=request.user)
    return render(request, "transactions/recurring_form.html", {"form": form})


@login_required
def recurring_update(request, pk):
    """정기 거래 수정."""
    obj = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == "POST":
        form = RecurringTransactionForm(request.POST, instance=obj, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("recurring_list")
    else:
        form = RecurringTransactionForm(instance=obj, user=request.user)
    return render(request, "transactions/recurring_form.html", {"form": form})


@login_required
def recurring_delete(request, pk):
    """정기 거래 삭제 확인 → POST 시 삭제."""
    obj = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == "POST":
        obj.delete()
        return redirect("recurring_list")
    return render(request, "transactions/recurring_confirm_delete.html", {"item": obj})


@login_required
def recurring_toggle(request, pk):
    """정기 거래 활성/비활성 토글 (POST only)."""
    obj = get_object_or_404(RecurringTransaction, pk=pk, user=request.user)
    if request.method == "POST":
        obj.is_active = not obj.is_active
        obj.save()
    return redirect("recurring_list")
