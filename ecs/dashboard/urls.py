from django.urls import path

from ecs.dashboard import views


urlpatterns = (
    path('', views.view_dashboard, name='dashboard'),
)
