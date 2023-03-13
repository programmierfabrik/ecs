from django.urls import path

from ecs.core.views import clinic as views

urlpatterns = (
    path('', views.administration, name='core.clinic.administration'),
)
