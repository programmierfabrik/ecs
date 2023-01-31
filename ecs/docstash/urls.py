from django.urls import path

from ecs.docstash import views


urlpatterns = (
    path('<str:docstash_key>/doc/<int:document_pk>/', views.download_document, name='docstash.download_document'),
    path('<str:docstash_key>/doc/<int:document_pk>/view/', views.view_document, name='docstash.view_document'),
)
