from django.urls import path

from ecs.core.views import comments as views

urlpatterns = (
    path('submission/(<int:submission_pk>)/', views.index, name='core.comments.index'),
    path('submission/(<int:submission_pk>)/new/', views.edit, name='core.comments.edit_by_submission_pk'),
    path('<int:pk>/edit/', views.edit, name='core.comments.edit'),
    path('<int:pk>/delete/', views.delete, name='core.comments.delete'),
    path('<int:pk>/attachment/', views.download_attachment, name='core.comments.download_attachment'),
    path('<int:pk>/attachment/view/', views.view_attachment, name='core.comments.view_attachment'),
)
