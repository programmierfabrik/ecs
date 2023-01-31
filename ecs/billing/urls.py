from django.urls import path

from ecs.billing import views


urlpatterns = (
    path('submissions/', views.submission_billing, name='billing.submission_billing'),
    path('invoice/<int:invoice_pk>/', views.view_invoice, name='billing.view_invoice'),
    path('invoice/<int:invoice_pk>/pdf/', views.invoice_pdf, name='billing.invoice_pdf'),
    path('invoices/', views.invoice_list, name='billing.invoice_list'),

    path('external_review/', views.external_review_payment, name='billing.external_review_payment'),
    path('payment/<int:payment_pk>/', views.view_checklist_payment, name='billing.view_checklist_payment'),
    path('payment/<int:payment_pk>/pdf/', views.checklist_payment_pdf, name='billing.checklist_payment_pdf'),
    path('payments/', views.checklist_payment_list, name='billing.checklist_payment_list'),
)
