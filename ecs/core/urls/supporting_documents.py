from django.urls import path

from ecs.core.views import supporting_documents as views

urlpatterns = (
    path('', views.administration, name='core.supporting_documents.administration'),
    path('create/', views.create, name='core.supporting_documents.create'),
    path('delete/<int:pk>/', views.delete, name='core.supporting_documents.delete'),
    path('download/<int:pk>/', views.download, name='core.supporting_documents.download'),
    path('update/<int:pk>/', views.update, name='core.supporting_documents.update'),
)
