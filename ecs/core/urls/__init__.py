from django.urls import include, path

from ecs.core.views import logo
from ecs.core.views.fieldhistory import field_history
from ecs.core.views.administration import advanced_settings
from ecs.core.views.autocomplete import autocomplete


urlpatterns = (
    path('logo/', logo, name='core.logo'),
    path('fieldhistory/<str:model_name>/<int:pk>/', field_history, name='core.field_history'),
    path('advanced_settings/', advanced_settings, name='core.advanced_settings'),
    path('autocomplete/<str:queryset_name>/', autocomplete, name='core.autocomplete'),

    path('submission/', include('ecs.core.urls.submission')),
    path('comments/', include('ecs.core.urls.comments')),
    path('catalog/', include('ecs.core.urls.catalog')),
    path('medical-category/', include('ecs.core.urls.medical_category'))
)
