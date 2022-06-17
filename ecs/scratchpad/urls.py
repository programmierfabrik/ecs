from django.urls import path, re_path

from ecs.scratchpad import views


urlpatterns = (
    re_path(r'^popup/(?:(?P<scratchpad_pk>\d+)/)?$', views.popup, name='scratchpad.popup'),
    path('popup/list/', views.popup_list),
)
