from django.urls import path

from ecs.core.views import medical_category as views

urlpatterns = (
    path('', views.administration),
    path('new', views.create_medical_category),
    path('<int:pk>', views.update_medical_category),
    path('toggle/<int:pk>', views.toggle_disabled),
)
