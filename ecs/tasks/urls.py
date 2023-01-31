from django.urls import path, re_path

from ecs.tasks import views


urlpatterns = (
    re_path(r'^list/(?:submission/(?P<submission_pk>\d+)/)?$', views.task_list, name='tasks.task_list'),
    re_path(r'^list/mine/(?:submission/(?P<submission_pk>\d+)/)?$', views.my_tasks, name='tasks.my_tasks'),
    path('<int:submission_pk>/task_backlog/', views.task_backlog, name='tasks.task_backlog'),
    path('<int:task_pk>/accept/', views.accept_task, name='tasks.accept_task'),
    path('<int:task_pk>/accept/full/', views.accept_task_full, name='tasks.accept_task_full'),
    path('accept/', views.accept_tasks, name='tasks.accept_tasks'),
    path('accept/full/', views.accept_tasks_full, name='tasks.accept_tasks_full'),
    path('<int:task_pk>/decline/', views.decline_task, name='tasks.decline_task'),
    path('<int:task_pk>/decline/full/', views.decline_task_full, name='tasks.decline_task_full'),
    path('<int:task_pk>/do/', views.do_task, name='tasks.do_task'),
    path('<int:task_pk>/preview/', views.preview_task, name='tasks.preview_task'),
    path('<int:task_pk>/delete/<int:submission_pk>/', views.delete_task, name='tasks.delete_task')
)
