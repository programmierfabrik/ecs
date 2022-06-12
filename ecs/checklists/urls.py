from django.conf import settings
from django.urls import path, re_path

from ecs.checklists import views


urlpatterns = (
    re_path(r'^(?P<checklist_pk>\d+)/comments/(?P<flavour>positive|negative)/', views.checklist_comments),
    path('(<int:checklist_pk>)/pdf/', views.checklist_pdf),
    path('create_task/submission/(<int:submission_pk>/', views.create_task),
    path('categorization_tasks/submissions/<int:submission_pk>/', views.categorization_tasks),
)

if settings.DEBUG:
    urlpatterns += (
        path('<int:checklist_pk>/pdf/debug/', views.checklist_pdf_debug),
    )
