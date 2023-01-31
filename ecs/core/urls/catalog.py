from django.urls import path, re_path

from ecs.core.views import submissions as views


urlpatterns = (
    re_path(r'^(?:(?P<year>\d+)/)?$', views.catalog, name='core.catalog'),
    path('json/', views.catalog_json),
)
