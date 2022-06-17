from django.conf import settings
from django.urls import path, re_path

from ecs.core.views import submissions as views
from ecs.tasks.views import task_backlog, delete_task
from ecs.communication.views import new_thread


urlpatterns = (
    path('<int:submission_pk>/tasks/log/', task_backlog),
    path('<int:submission_pk>/task/<int:task_pk>/delete/', delete_task),

    path('<int:submission_pk>/messages/new/', new_thread),

    path('list/all/', views.all_submissions, name='core.submission.all_submissions'),
    path('list/xls/', views.xls_export, name='core.submission.xls_export'),
    re_path(r'^list/xls/(?P<shasum>[0-9a-f]{40})/$', views.xls_export_download),
    path('list/assigned/', views.assigned_submissions, name='core.submission.assigned_submissions'),
    path('list/mine/', views.my_submissions, name='core.submission.my_submissions'),

    path('import/', views.import_submission_form, name='core.submission.import_submission_form'),
    re_path(r'^new/(?:(?P<docstash_key>.+)/)?$', views.create_submission_form, name='core.submission.create_submission_form'),
    path('delete/<str:docstash_key>/', views.delete_docstash_entry, name='core.submission.delete_docstash_entry'),
    path('doc/upload/<str:docstash_key>/', views.upload_document_for_submission, name='core.submission.upload_document_for_submission'),
    path('doc/delete/<str:docstash_key>/', views.delete_document_from_submission, name='core.submission.delete_document_from_submission'),

    path('diff/forms/<int:old_submission_form_pk>/<int:new_submission_form_pk>/', views.diff, name='core.submission.diff'),

    path('<int:submission_pk>/', views.view_submission, name='view_submission'),
    path('<int:submission_pk>/copy/', views.copy_latest_submission_form, name='core.submission.copy_latest_submission_form'),
    path('<int:submission_pk>/amend/<int:notification_type_pk>/', views.copy_latest_submission_form, name='core.submission.copy_latest_submission_form_by_notification_pk'),
    path('<int:submission_pk>/export/', views.export_submission, name='core.submission.export_submission'),
    path('<int:submission_pk>/presenter/change/', views.change_submission_presenter, name='core.submission.change_submission_presenter'),
    path('<int:submission_pk>/susar_presenter/change/', views.change_submission_susar_presenter, name='core.submission.change_submission_susar_presenter'),

    path('<int:submission_pk>/temp-auth/grant/', views.grant_temporary_access, name='core.submission.grant_temporary_access'),
    path('<int:submission_pk>/temp-auth/<int:temp_auth_pk>/revoke/', views.revoke_temporary_access, name='core.submission.revoke_temporary_access'),
    path('<int:submission_pk>/review/checklist/<int:blueprint_pk>/reopen/', views.reopen_checklist, name='core.submission.reopen_checklist'),

    path('form/<int:submission_form_pk>/', views.readonly_submission_form, name='readonly_submission_form'),
    path('form/<int:submission_form_pk>/pdf/', views.submission_form_pdf, name='core.submission.submission_form_pdf'),
    path('form/<int:submission_form_pk>/pdf/view/', views.submission_form_pdf_view, name='core.submission.submission_form_pdf_view'),
    path('form/<int:submission_form_pk>/doc/<int:document_pk>/', views.download_document, name='core.submission.download_document'),
    path('form/<int:submission_form_pk>/doc/<int:document_pk>/view/', views.view_document, name='core.submission.view_document'),
    path('form/<int:submission_form_pk>/copy/', views.copy_submission_form),
    path('form/<int:submission_form_pk>/amend/<int:notification_type_pk>/', views.copy_submission_form),
    path('form/<int:submission_form_pk>/review/checklist/<int:blueprint_pk>/', views.checklist_review),
    path('form/<int:submission_form_pk>/review/checklist/show/<int:checklist_pk>/', views.show_checklist_review),
    path('form/<int:submission_form_pk>/review/checklist/drop/<int:checklist_pk>/', views.drop_checklist_review, name='core.submission.drop_checklist_review'),
    path('<int:submission_pk>/categorization/', views.categorization),
    path('<int:submission_pk>/categorization/reopen/', views.reopen_categorization, name='core.submission.reopen_categorization'),
    path('<int:submission_pk>/review/categorization/', views.categorization_review),
    path('form/<int:submission_pk>/review/initial/', views.initial_review),
    path('form/<int:submission_pk>/review/paper_submission/', views.paper_submission_review),
    path('form/<int:submission_pk>/biased/', views.biased_board_members, name='core.submission.biased_board_members'),
    path('form/<int:submission_pk>/biased/remove/<int:user_pk>/', views.remove_biased_board_member, name='core.submission.remove_biased_board_member'),
    path('form/<int:submission_form_pk>/review/vote/', views.vote_review),
    path('form/<int:submission_form_pk>/vote/prepare/', views.vote_preparation),
    path('form/<int:submission_form_pk>/vote/prepare/', views.vote_preparation),
    path('form/<int:submission_form_pk>/vote/b2-prepare/', views.b2_vote_preparation),
)

if settings.DEBUG:
    urlpatterns += (
        path('form/<int:submission_form_pk>/pdf/debug/', views.submission_form_pdf_debug, name='core.submission.submission_form_pdf_debug'),
    )
