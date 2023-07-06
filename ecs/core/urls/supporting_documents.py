from django.urls import path

from ecs.core.views import supporting_documents as views

urlpatterns = (
    path('', views.administration, name='core.supporting_documents.administration'),
    path('create/', views.create, name='core.supporting_documents.create'),
)
