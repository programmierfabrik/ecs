from django.conf import settings
from django.urls import path, re_path

from ecs.notifications import views


urlpatterns = (
    path('new/', views.select_notification_creation_type, name='notification.select_notification_creation_type'),
    path('new/<int:notification_type_pk>/diff/<int:submission_form_pk>/', views.create_diff_notification, name='notifications.create_diff_notification'),
    re_path(r'^new/(?P<notification_type_pk>\d+)/(?:(?P<docstash_key>.+)/)?$', views.create_notification, name='notifications.create_notification'),
    path('delete/<str:docstash_key>/', views.delete_docstash_entry, name='notifications.delete_docstash_entry'),
    path('doc/upload/<str:docstash_key>/', views.upload_document_for_notification, name='notifications.upload_document_for_notification'),
    path('doc/delete/<str:docstash_key>/', views.delete_document_from_notification, name='notifications.delete_document_from_notification'),
    path('submission_data_for_notification/', views.submission_data_for_notification, name='notifications.submission_data_for_notification'),
    path('investigators_for_notification/', views.investigators_for_notification, name='notification.investigators_for_notification'),
    path('<int:notification_pk>/', views.view_notification, name='notifications.view_notification'),
    path('<int:notification_pk>/pdf/', views.notification_pdf, name='notifications.notification_pdf'),
    path('<int:notification_pk>/doc/<int:document_pk>/', views.download_document, name='notifications.download_document'),
    path('<int:notification_pk>/doc/<int:document_pk>/view/', views.view_document, name='notifications.view_document'),
    path('<int:notification_pk>/answer/pdf/', views.notification_answer_pdf, name='notifications.notification_answer_pdf'),
    path('<int:notification_pk>/answer/edit/', views.edit_notification_answer, name='notifications.edit_notification_answer'),
    path('<int:notification_pk>/answer/sign/', views.notification_answer_sign, name='notifications.notification_answer_sign'),
    path('list/open/', views.open_notifications, name='notifications.open_notifications'),
)

if settings.DEBUG:
    urlpatterns += (
        path('<int:notification_pk>/pdf/debug/', views.notification_pdf_debug, name='notifications.notification_pdf_debug'),
        path('<int:notification_pk>/answer/pdf/debug/', views.notification_answer_pdf_debug, name='notifications.notification_answer_pdf_debug'),
    )
