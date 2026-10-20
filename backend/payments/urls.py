from django.urls import path

from payments import views

urlpatterns = [
    path("payments/", views.payment_collection_view, name="payment-collection"),
    path("payments/<int:payment_id>/", views.payment_detail_view, name="payment-detail"),
    path("payments/<int:payment_id>/submit/", views.payment_submit_view, name="payment-submit"),
    path("payments/<int:payment_id>/approve/", views.payment_approve_view, name="payment-approve"),
    path("payments/<int:payment_id>/reject/", views.payment_reject_view, name="payment-reject"),
    path("payments/<int:payment_id>/remind/", views.payment_remind_view, name="payment-remind"),
    path("payments/<int:payment_id>/refund/", views.payment_refund_view, name="payment-refund"),
    path("payments/<int:payment_id>/attachments/", views.payment_attachment_collection_view, name="payment-attachments"),
    path(
        "payments/<int:payment_id>/attachments/<int:attachment_id>/download/",
        views.payment_attachment_download_view,
        name="payment-attachment-download",
    ),
    path("refunds/", views.refund_collection_view, name="refund-collection"),
    path("refunds/<int:refund_id>/", views.refund_detail_view, name="refund-detail"),
    path("refunds/<int:refund_id>/approve/", views.refund_approve_view, name="refund-approve"),
    path("refunds/<int:refund_id>/reject/", views.refund_reject_view, name="refund-reject"),
    path("refunds/<int:refund_id>/complete/", views.refund_complete_view, name="refund-complete"),
    path("payments/<int:payment_id>/charges/", views.payment_charge_view, name="payment-charge"),
    path("payments/<int:payment_id>/penalties/", views.payment_penalty_view, name="payment-penalty"),
    path("charges/<int:charge_id>/void/", views.charge_void_view, name="charge-void"),
]
