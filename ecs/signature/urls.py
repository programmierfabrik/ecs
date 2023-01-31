import sys

from django.urls import path, re_path

from ecs.signature import views


urlpatterns = (
    path('batch/<int:sign_session_id>/', views.batch_sign, name='signature.batch_sign'),
    path('send/<int:pdf_id>/', views.sign_send, name='signature.sign_send'),
    path('error/<int:pdf_id>/', views.sign_error, name='signature.sign_error'),
    path('preview/<int:pdf_id>/', views.sign_preview, name='signature.sign_preview'),
    re_path(r'^action/(?P<pdf_id>\d+)/(?P<action>[^/]+)/$', views.batch_action, name='signature.batch_action'),
    path('receive/<int:pdf_id>/', views.sign_receive, name='signature.sign_receive'),
)

if 'test' in sys.argv:
    from ecs.signature.tests import sign_success, sign_fail
    urlpatterns += (
        path('test/success/', sign_success, name='signature.sign_success'),
        path('test/failure/', sign_fail, name='signature.sign_fail'),
    )
