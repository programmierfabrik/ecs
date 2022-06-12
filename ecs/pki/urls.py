from django.urls import path

from ecs.pki import views


urlpatterns = (
    path('pki/certs/new/', views.create_cert),
    path('pki/certs/', views.cert_list),
    path('pki/certs/<int:cert_pk>/revoke/', views.revoke_cert),
)
