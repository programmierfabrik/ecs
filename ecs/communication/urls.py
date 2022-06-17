from django.urls import path, re_path

from ecs.communication import views


urlpatterns = (
    re_path(r'^list/(?:(?P<submission_pk>\d+)/)?$', views.list_threads, name='communication.list_threads'),
    path('widget/', views.dashboard_widget),
    path('widget/overview/<int:submission_pk>/', views.communication_overview_widget),
    re_path(r'^new/(?:(?P<submission_pk>\d+)/)?(?:(?P<to_user_pk>\d+)/)?$', views.new_thread),
    path('<int:thread_pk>/read/', views.read_thread),
    path('<int:thread_pk>/mark_read/', views.mark_read),
    path('<int:thread_pk>/star/', views.star),
    path('<int:thread_pk>/unstar/', views.unstar),
)
