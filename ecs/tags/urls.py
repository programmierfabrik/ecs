from django.urls import path

from ecs.tags import views


urlpatterns = (
    path('', views.index),
    path('new/', views.edit),
    path('<int:pk>/edit/', views.edit),
    path('<int:pk>/delete/', views.delete),
    path('assign/submission/<int:submission_pk>', views.assign),
)
