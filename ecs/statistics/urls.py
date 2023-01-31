from django.urls import re_path

from ecs.statistics import views


urlpatterns = (
    re_path(r'^(?:(?P<year>\d{4})/)?$', views.stats, name='statistics.stats'),
)
