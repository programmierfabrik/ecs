from django.urls import path

from ecs.core.views import comments as views

urlpatterns = (
    path('submission/(<int:submission_pk>)/', views.index),
    path('submission/(<int:submission_pk>)/new/', views.edit),
    path('<int:pk>/edit/', views.edit),
    path('<int:pk>/delete/', views.delete),
    path('<int:pk>/attachment/', views.download_attachment),
    path('<int:pk>/attachment/view/', views.view_attachment),
)
