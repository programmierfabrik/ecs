from django.urls import path

from ecs.core.views import medical_category as views

urlpatterns = (
    path('', views.administration, name='core.medical_category.administration'),
    path('new', views.create_medical_category, name='core.medical_category.create_medical_category'),
    path('<int:pk>', views.update_medical_category, name='core.medical_category.update_medical_category'),
    path('toggle/<int:pk>', views.toggle_disabled, name='core.medical_category.toggle_disabled'),
)
