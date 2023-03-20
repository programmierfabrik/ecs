from django.urls import path, re_path

from ecs.meetings import views


urlpatterns = (
    path('reschedule/submission/<int:submission_pk>/', views.reschedule_submission, name='meetings.reschedule_submission'),

    path('new/', views.create_meeting, name='meetings.create_meeting'),
    path('next/', views.next, name='meetings.next'),
    path('list/upcoming/', views.upcoming_meetings, name='meetings.upcoming_meetings'),
    path('list/past/', views.past_meetings, name='meetings.past_meetings'),
    path('<int:meeting_pk>/', views.meeting_details, name='meetings.meeting_details'),
    path('<int:meeting_pk>/constraints_for_user/<int:user_pk>/', views.edit_user_constraints, name='meetings.edit_user_constraints'),
    path('<int:meeting_pk>/edit/', views.edit_meeting, name='meetings.edit_meeting'),
    path('<int:meeting_pk>/open_tasks/', views.open_tasks, name='meetings.open_tasks'),
    path('<int:meeting_pk>/submissions/', views.submission_list, name='meetings.submission_list'),
    path('<int:meeting_pk>/notifications/', views.notification_list, name='meetings.notification_list'),
    path('<int:meeting_pk>/document/<int:document_pk>/', views.download_document, name='meetings.download_document'),
    path('<int:meeting_pk>/document/<int:document_pk>/view/', views.view_document, name='meetings.view_document'),
    path('<int:meeting_pk>/documents/zip/', views.download_zipped_documents, name='meetings.download_zipped_documents_by_meeting_pk'),
    path('<int:meeting_pk>/documents/<int:submission_pk>/zip/', views.download_zipped_documents, name='meetings.download_zipped_documents'),

    path('<int:meeting_pk>/timetable/', views.timetable_editor, name='meetings.timetable_editor'),
    re_path(r'^(?P<meeting_pk>\d+)/timetable/optimize/(?P<algorithm>random|brute_force|ga)/$', views.optimize_timetable, name='meetings.optimize_timetable'),
    re_path(r'^(?P<meeting_pk>\d+)/timetable/optimize/(?P<algorithm>random|brute_force|ga)/long/$', views.optimize_timetable_long, name='meetings.optimize_timetable_long'),
    path('<int:meeting_pk>/timetable/entry/new/', views.add_timetable_entry),
    path('<int:meeting_pk>/timetable/entry/add/', views.add_free_timetable_entry, name='meetings.add_free_timetable_entry'),
    path('<int:meeting_pk>/timetable/entry/move/', views.move_timetable_entry, name='meetings.move_timetable_entry'),
    path('<int:meeting_pk>/timetable/entry/<int:entry_pk>/delete/', views.remove_timetable_entry, name='meetings.remove_timetable_entry'),
    path('<int:meeting_pk>/timetable/entry/<int:entry_pk>/update/', views.update_timetable_entry, name='meetings.update_timetable_entry'),
    path('<int:meeting_pk>/timetable/entry/<int:entry_pk>/users/<int:user_pk>/toggle/', views.toggle_participation, name='meetings.toggle_participation'),

    path('<int:meeting_pk>/assistant/', views.meeting_assistant, name='meetings.meeting_assistant'),
    path('<int:meeting_pk>/assistant/start/', views.meeting_assistant_start, name='meetings.meeting_assistant_start'),
    path('<int:meeting_pk>/assistant/stop/', views.meeting_assistant_stop, name='meetings.meeting_assistant_stop'),
    path('<int:meeting_pk>/assistant/<int:top_pk>/', views.meeting_assistant_top, name='meetings.meeting_assistant_top'),
    path('<int:meeting_pk>/assistant/quickjump/', views.meeting_assistant_quickjump, name='meetings.meeting_assistant_quickjump'),
    path('<int:meeting_pk>/assistant/comments/', views.meeting_assistant_comments, name='meetings.meeting_assistant_comments'),
    path('<int:meeting_pk>/assistant/other_tops/', views.meeting_assistant_other_tops, name='meetings.meeting_assistant_other_tops'),

    path('<int:meeting_pk>/agenda/pdf/', views.agenda_pdf, name='meetings.agenda_pdf'),
    path('<int:meeting_pk>/agenda/send/', views.send_agenda_to_board, name='meetings.send_agenda_to_board'),
    path('<int:meeting_pk>/expedited_reviewer_invitations/send/', views.send_expedited_reviewer_invitations, name='meetings.send_expedited_reviewer_invitations'),
    path('<int:meeting_pk>/timetable_pdf/', views.timetable_pdf, name='meetings.timetable_pdf'),
    path('<int:meeting_pk>/timetablepart/', views.timetable_htmlemailpart),
    path('<int:meeting_pk>/protocol/edit/', views.edit_protocol, name='meetings.edit_protocol'),
    path('<int:meeting_pk>/protocol/pdf/render/', views.render_protocol_pdf, name='meetings.render_protocol_pdf'),
    path('<int:meeting_pk>/protocol/pdf/', views.protocol_pdf, name='meetings.protocol_pdf'),
    path('<int:meeting_pk>/protocol/send/', views.send_protocol, name='meetings.send_protocol'),
    path('<int:meeting_pk>/protocol/clinic/', views.list_submissions_protocols, name='meetings.list_submissions_protocols'),
    path('<int:meeting_pk>/protocol/clinic/pdf/render', views.render_all_possible_protocols, name='meetings.render_all_possible_protocols'),
    path('<int:meeting_pk>/protocol/clinic/pdf/render/<int:submission_pk>/', views.render_submission_protocol, name='meetings.render_submission_protocol'),
    path('<int:meeting_pk>/protocol/clinic/pdf/<int:protocol_pk>/', views.submission_protocol_pdf, name='meetings.submission_protocol_pdf'),
    path('<int:meeting_pk>/protocol/clinic/pdf/send/', views.send_all_possible_submission_protocol, name='meetings.send_all_possible_submission_protocol'),
    path('<int:meeting_pk>/protocol/clinic/pdf/send/<int:submission_pk>/', views.send_submission_protocol, name='meetings.send_submission_protocol'),
)
