from django.urls import path, re_path

from ecs.tasks import views


urlpatterns = (
    re_path(r'^list/(?:submission/(?P<submission_pk>\d+)/)?$', views.task_list),
    re_path(r'^list/mine/(?:submission/(?P<submission_pk>\d+)/)?$', views.my_tasks),
    path('<int:task_pk>/accept/', views.accept_task),
    path('<int:task_pk>/accept/full/', views.accept_task_full),
    path('accept/', views.accept_tasks),
    path('accept/full/', views.accept_tasks_full),
    path('<int:task_pk>/decline/', views.decline_task),
    path('<int:task_pk>/decline/full/', views.decline_task_full),
    path('<int:task_pk>/do/', views.do_task),
    path('<int:task_pk>/preview/', views.preview_task),
)
