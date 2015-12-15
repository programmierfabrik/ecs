from django.conf.urls.defaults import *

urlpatterns = patterns('ecs.meetings.views',
    url(r'^reschedule/submission/(?P<submission_pk>\d+)/', 'reschedule_submission'),

    url(r'^new/$', 'create_meeting'),
    url(r'^next/$', 'next'),
    url(r'^list/upcoming/$', 'upcoming_meetings'),
    url(r'^list/past/$', 'past_meetings'),
    url(r'^(?P<meeting_pk>\d+)/$', 'meeting_details'),
    url(r'^(?P<meeting_pk>\d+)/constraints_for_user/(?P<user_pk>\d+)/$', 'edit_user_constraints'),
    url(r'^(?P<meeting_pk>\d+)/edit/$', 'edit_meeting'),
    url(r'^(?P<meeting_pk>\d+)/open_tasks/$', 'open_tasks'),
    url(r'^(?P<meeting_pk>\d+)/tops/$', 'tops'),
    url(r'^(?P<meeting_pk>\d+)/submissions/$', 'submission_list'),
    url(r'^(?P<meeting_pk>\d+)/documents/zip/$', 'download_zipped_documents'),
    url(r'^(?P<meeting_pk>\d+)/documents/(?P<submission_pk>\d+)/zip/$', 'download_zipped_documents'),

    url(r'^(?P<meeting_pk>\d+)/timetable/$', 'timetable_editor'),
    url(r'^(?P<meeting_pk>\d+)/timetable/optimize/(?P<algorithm>random|brute_force|ga)/$', 'optimize_timetable'),
    url(r'^(?P<meeting_pk>\d+)/timetable/optimize/(?P<algorithm>random|brute_force|ga)/long/$', 'optimize_timetable_long'),
    url(r'^(?P<meeting_pk>\d+)/timetable/entry/new/$', 'add_timetable_entry'),
    url(r'^(?P<meeting_pk>\d+)/timetable/entry/add/$', 'add_free_timetable_entry'),
    url(r'^(?P<meeting_pk>\d+)/timetable/entry/move/$', 'move_timetable_entry'),
    url(r'^(?P<meeting_pk>\d+)/timetable/entry/(?P<entry_pk>\d+)/delete/$', 'remove_timetable_entry'),
    url(r'^(?P<meeting_pk>\d+)/timetable/entry/(?P<entry_pk>\d+)/update/$', 'update_timetable_entry'),
    url(r'^(?P<meeting_pk>\d+)/timetable/entry/(?P<entry_pk>\d+)/users/(?P<user_pk>\d+)/toggle/$', 'toggle_participation'),

    url(r'^(?P<meeting_pk>\d+)/assistant/$', 'meeting_assistant'),
    url(r'^(?P<meeting_pk>\d+)/assistant/start/$', 'meeting_assistant_start'),
    url(r'^(?P<meeting_pk>\d+)/assistant/stop/$', 'meeting_assistant_stop'),
    url(r'^(?P<meeting_pk>\d+)/assistant/(?P<top_pk>\d+)/$', 'meeting_assistant_top'),
    url(r'^(?P<meeting_pk>\d+)/assistant/quickjump/$', 'meeting_assistant_quickjump'),
    url(r'^(?P<meeting_pk>\d+)/assistant/comments/$', 'meeting_assistant_comments'),
    url(r'^(?P<meeting_pk>\d+)/assistant/retrospective_thesis_expedited/$', 'meeting_assistant_retrospective_thesis_expedited'),

    url(r'^(?P<meeting_pk>\d+)/agenda/pdf/$', 'agenda_pdf'),
    url(r'^(?P<meeting_pk>\d+)/agenda/send/$', 'send_agenda_to_board'),
    url(r'^(?P<meeting_pk>\d+)/expedited_reviewer_invitations/send/$', 'send_expedited_reviewer_invitations'),
    url(r'^(?P<meeting_pk>\d+)/timetable_pdf/$', 'timetable_pdf'),
    url(r'^(?P<meeting_pk>\d+)/timetablepart/$', 'timetable_htmlemailpart'),
    url(r'^(?P<meeting_pk>\d+)/protocol/pdf/$', 'protocol_pdf'),
    url(r'^(?P<meeting_pk>\d+)/protocol/send/$', 'send_protocol'),
)