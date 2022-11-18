from django.urls import re_path

from ecs.documents import views


urlpatterns = (
    re_path(r'^ref/(?P<ref_key>[0-9a-f]{32})$', views.download_once, name='documents.download_once'),
)
