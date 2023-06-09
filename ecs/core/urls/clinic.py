from django.urls import path

from ecs.core.views import clinic as views

urlpatterns = (
    path('', views.administration, name='core.clinic.administration'),
    path('new/', views.upsert_clinic, name='core.clinic.create_clinic'),
    path('<int:clinic_id>', views.upsert_clinic, name='core.clinic.update_clinic'),
)
