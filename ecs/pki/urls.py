from django.urls import path

from ecs.pki import views


urlpatterns = (
    path('pki/certs/new/', views.create_cert, name='pki.create_cert'),
    path('pki/certs/', views.cert_list, name='pki.cert_list'),
    path('pki/certs/soon-expired', views.list_soon_to_be_expired_certs, name='pki.list_soon_to_be_expired_certs'),
    path('pki/certs/<int:cert_pk>/revoke/', views.revoke_cert, name='pki.revoke_cert'),
)
