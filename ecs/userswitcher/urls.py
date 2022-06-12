from django.urls import path

from ecs.userswitcher import views


urlpatterns = (
    path('switch/', views.switch),
)
