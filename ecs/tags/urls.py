from django.urls import path

from ecs.tags import views


urlpatterns = (
    path('', views.index, name='tags.index'),
    path('new/', views.edit),
    path('<int:pk>/edit/', views.edit, name='tags.edit'),
    path('<int:pk>/delete/', views.delete, name='tags.delete'),
    path('assign/submission/<int:submission_pk>', views.assign, name='tags.assign'),
)
