from django.urls import path

from ecs.core.views import clinic as views

urlpatterns = (
    path('', views.administration, name='core.clinic.administration'),
    path('new/', views.create_clinic, name='core.clinic.create_clinic'),
    # path('<int:pk>', views.update_medical_category, name='core.medical_category.update_medical_category'),
    # path('toggle/<int:pk>', views.toggle_disabled, name='core.medical_category.toggle_disabled'),
)
