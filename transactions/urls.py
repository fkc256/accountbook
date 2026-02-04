"""transactions 앱 URL 설정 — 계좌·거래·영수증·정기거래 엔드포인트."""

from django.urls import path
from . import views

urlpatterns = [
    # Account CRUD
    path("accounts/", views.account_list, name="account_list"),
    path("accounts/new/", views.account_create, name="account_create"),
    path("accounts/<int:pk>/", views.account_detail, name="account_detail"),
    path("accounts/<int:pk>/edit/", views.account_update, name="account_update"),
    path("accounts/<int:pk>/delete/", views.account_delete, name="account_delete"),

    # Transaction CRUD
    path("", views.transaction_list, name="transaction_list"),
    path("new/", views.transaction_create, name="transaction_create"),
    path("<int:pk>/", views.transaction_detail, name="transaction_detail"),
    path("<int:pk>/edit/", views.transaction_update, name="transaction_update"),
    path("<int:pk>/delete/", views.transaction_delete, name="transaction_delete"),

    # Attachment
    path("<int:tx_pk>/attachment/upload/", views.attachment_upload, name="attachment_upload"),
    path("<int:tx_pk>/attachment/delete/", views.attachment_delete, name="attachment_delete"),

    # RecurringTransaction
    path("recurring/", views.recurring_list, name="recurring_list"),
    path("recurring/new/", views.recurring_create, name="recurring_create"),
    path("recurring/<int:pk>/edit/", views.recurring_update, name="recurring_update"),
    path("recurring/<int:pk>/delete/", views.recurring_delete, name="recurring_delete"),
    path("recurring/<int:pk>/toggle/", views.recurring_toggle, name="recurring_toggle"),
]
