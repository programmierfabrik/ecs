# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import tempfile
import zipfile
import hashlib
import os

from django.conf import settings
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils import simplejson
from django.contrib.auth.models import User
from django.utils.datastructures import SortedDict
from django.utils.translation import ugettext as _
from django.template.defaultfilters import slugify
from django.contrib.contenttypes.models import ContentType
from django.core.servers.basehttp import FileWrapper
from django.core.paginator import Paginator, EmptyPage, InvalidPage

from ecs.utils.viewutils import render, render_html, render_pdf, pdf_response
from ecs.users.utils import user_flag_required, user_group_required, sudo
from ecs.core.models import Submission, MedicalCategory, ExpeditedReviewCategory
from ecs.core.models.constants import SUBMISSION_LANE_BOARD, SUBMISSION_TYPE_MULTICENTRIC
from ecs.checklists.models import Checklist, ChecklistBlueprint
from ecs.votes.models import Vote
from ecs.votes.forms import VoteForm, SaveVoteForm
from ecs.tasks.models import Task
from ecs.ecsmail.utils import deliver

from ecs.utils.security import readonly
from ecs.meetings.tasks import optimize_timetable_task
from ecs.meetings.signals import on_meeting_end
from ecs.meetings.models import Meeting, Participation, TimetableEntry, AssignedMedicalCategory, Participation
from ecs.meetings.forms import (MeetingForm, TimetableEntryForm, FreeTimetableEntryForm, UserConstraintFormSet, 
    SubmissionReschedulingForm, AssignedMedicalCategoryFormSet, MeetingAssistantForm, ExpeditedVoteFormSet,
    ExpeditedReviewerInvitationForm)
from ecs.votes.constants import FINAL_VOTE_RESULTS
from ecs.communication.utils import send_system_message_template
from ecs.documents.models import Document


@user_flag_required('is_internal')
@user_group_required('EC-Office')
def create_meeting(request):
    form = MeetingForm(request.POST or None)
    if form.is_valid():
        meeting = form.save()
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_details', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/form.html', {
        'form': form,
    })

@readonly()
@user_flag_required('is_internal', 'is_resident_member')
def meeting_list(request, meetings, title=None):
    if not title:
        title = _('Meetings')
    paginator = Paginator(meetings, 12)
    try:
        meetings = paginator.page(int(request.GET.get('page', '1')))
    except (EmptyPage, InvalidPage):
        meetings = paginator.page(1)
    return render(request, 'meetings/list.html', {
        'meetings': meetings,
        'title': title,
    })

@readonly()
@user_flag_required('is_internal', 'is_resident_member')
def upcoming_meetings(request):
    return meeting_list(request, Meeting.objects.filter(start__gte=datetime.now()).order_by('start'), title=_('Upcoming Meetings'))

@readonly()
@user_flag_required('is_internal', 'is_resident_member')
def past_meetings(request):
    return meeting_list(request, Meeting.objects.filter(start__lt=datetime.now()).order_by('-start'), title=_('Past Meetings'))

@user_flag_required('is_executive_board_member')
def reschedule_submission(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    form = SubmissionReschedulingForm(request.POST or None, submission=submission)
    if form.is_valid():
        from_meeting = form.cleaned_data['from_meeting']
        to_meeting = form.cleaned_data['to_meeting']
        old_entries = from_meeting.timetable_entries.filter(submission=submission)

        for entry in old_entries:
            Participation.objects.filter(entry=entry).delete()
            visible = (not entry.timetable_index is None)
            entry.submission = None
            entry.save()
            entry.delete() # FIXME: study gets deleted if there is a vote. We should never use delete
            to_meeting.add_entry(submission=submission, duration=entry.duration, title=entry.title, visible=visible)
            with sudo():
                new_experts = list(AssignedMedicalCategory.objects.filter(meeting=to_meeting, board_member__isnull=False, category__pk__in=submission.medical_categories.values('pk').query).values_list('board_member__pk', flat=True))
                tasks = Task.objects.for_data(submission).filter(
                    task_type__workflow_node__uid='board_member_review', closed_at=None, deleted_at__isnull=True).exclude(assigned_to__pk__in=new_experts)
                tasks.mark_deleted()
        submission.update_next_meeting()
        return HttpResponseRedirect(reverse('view_submission', kwargs={'submission_pk': submission.pk}))
    return render(request, 'meetings/reschedule.html', {
        'submission': submission,
        'form': form,
    })

@user_flag_required('is_internal')
def open_tasks(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    open_tasks = SortedDict()
    for top in meeting.timetable_entries.filter(submission__isnull=False).order_by('timetable_index', 'submission__ec_number').select_related('submission', 'submission__current_submission_form'):
        with sudo():
            ts = list(Task.objects.for_submission(top.submission).filter(closed_at__isnull=True, deleted_at__isnull=True).select_related('task_type', 'assigned_to', 'assigned_to__ecs_profile'))
        if len(ts):
            open_tasks[top] = ts
    
    return render(request, 'meetings/tabs/open_tasks.html', {
        'meeting': meeting,
        'open_tasks': open_tasks,
    })

@user_flag_required('is_internal', 'is_resident_member', 'is_board_member')
@user_group_required('EC-Office', 'EC-Executive Board Group', 'EC-Signing Group')
def tops(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    tops = list(meeting.timetable_entries.order_by('timetable_index', 'submission__ec_number').select_related('submission', 'submission__current_submission_form'))

    next_tops = [t for t in tops if t.is_open][:3]
    closed_tops = [t for t in tops if not t.is_open]

    open_tops = SortedDict()
    for top in [t for t in tops if t.is_open]:
        if top.submission:
            medical_categories = meeting.medical_categories.exclude(board_member__isnull=True).filter(
                category__in=top.submission.medical_categories.values('pk').query)
            bms = tuple(User.objects.filter(pk__in=medical_categories.values('board_member').query).order_by('pk').distinct())
        else:
            bms = ()
        if bms in open_tops:
            open_tops[bms].append(top)
        else:
            open_tops[bms] = [top]
    
    def board_member_cmp(a, b):
        if not a:
            return 1
        if not b:
            return -1
        return a < b

    open_tops.keyOrder = list(sorted(open_tops.keys(), cmp=board_member_cmp))
    

    return render(request, 'meetings/tabs/tops.html', {
        'meeting': meeting,
        'next_tops': next_tops,
        'open_tops': open_tops,
        'closed_tops': closed_tops,
    })


@user_flag_required('is_internal', 'is_resident_member')
def submission_list(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    tops = list(meeting.timetable_entries.filter(timetable_index__isnull=False).order_by('timetable_index'))
    tops += list(meeting.timetable_entries.filter(timetable_index__isnull=True).order_by('pk'))
    return render(request, 'meetings/tabs/submissions.html', {
        'meeting': meeting,
        'tops': tops,
    })


@user_flag_required('is_internal', 'is_resident_member')
def download_zipped_documents(request, meeting_pk=None, submission_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    
    doctypes = ('patientinformation', 'checklist')
    files = set()
    
    filename_bits = [slugify(meeting.title)]

    checklist_ct = ContentType.objects.get_for_model(Checklist)
    def _add(submission):
        sf = submission.current_submission_form
        docs = sf.documents.filter(doctype__identifier__in=doctypes).exclude(status='deleted')
        docs |= Document.objects.filter(content_type=checklist_ct, object_id__in=Checklist.objects.filter(status='review_ok', submission=submission))
        for doc in docs.order_by('pk'):
            files.add((submission, doc))
        files.add((submission, sf.pdf_document))

    with sudo():
        if submission_pk:
            submission = get_object_or_404(meeting.submissions, pk=submission_pk)
            _add(submission)
            filename_bits.append(submission.get_filename_slice())
        else:
            for submission in meeting.submissions.order_by('pk'):
                _add(submission)

    h = hashlib.sha1()
    for submission, doc in files:
        h.update('(%s:%s)' % (submission.pk, doc.pk))

    cache_file = os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, '%s.zip' % h.hexdigest())
    
    if not os.path.exists(cache_file):
        zf = zipfile.ZipFile(cache_file, 'w')
        try:
            for submission, doc in files:
                with doc.as_temporary_file() as docfile:
                    path = [submission.get_filename_slice(), doc.get_filename()]
                    if not submission_pk:
                        path.insert(0, submission.get_workflow_lane_display())
                    zf.write(docfile.name, '/'.join(path))
        finally:
            zf.close()
    else:
        os.utime(cache_file, None)

    response = HttpResponse(FileWrapper(open(cache_file, 'r')), content_type='application/zip')
    response['Content-Disposition'] = 'attachment;filename=%s.zip' % '.'.join(filename_bits)
    return response


@user_flag_required('is_internal')
@user_group_required('EC-Office')
def add_free_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    form = FreeTimetableEntryForm(request.POST or None)
    if form.is_valid():
        entry = meeting.add_entry(**form.cleaned_data)
        return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/timetable/add_free_entry.html', {
        'form': form,
        'meeting': meeting,
    })

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def add_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    is_break = request.GET.get('break', False)
    if is_break:
        entry = meeting.add_break(duration=timedelta(minutes=30))
    else:
        entry = meeting.add_entry(duration=timedelta(minutes=7, seconds=30), submission=Submission.objects.order_by('?')[:1].get())
        import random
        for user in User.objects.order_by('?')[:random.randint(1, 4)]:
            Participation.objects.create(entry=entry, user=user)
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def remove_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    entry = get_object_or_404(TimetableEntry, pk=entry_pk)
    if entry.submission:
        raise Http404(_("only tops without associated submission can be deleted"))
    entry.delete()
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def update_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    entry = get_object_or_404(TimetableEntry, pk=entry_pk)
    form = TimetableEntryForm(request.POST)
    if form.is_valid():
        entry.duration = form.cleaned_data['duration']
        entry.optimal_start = form.cleaned_data['optimal_start']
        entry.save()
        if entry.optimal_start:
            entry.move_to_optimal_position()
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
@user_flag_required('is_internal')
@user_group_required('EC-Office')
def toggle_participation(request, meeting_pk=None, user_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    p = get_object_or_404(Participation, user=user_pk, entry=entry_pk)
    p.ignored_for_optimization = not p.ignored_for_optimization
    p.save()
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def move_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    from_index = int(request.GET.get('from_index'))
    to_index = int(request.GET.get('to_index'))
    meeting[from_index].index = to_index
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

@readonly()
@user_flag_required('is_internal')
@user_group_required('EC-Office')
def timetable_editor(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    from ecs.meetings.tasks import _eval_timetable
    return render(request, 'meetings/timetable/editor.html', {
        'meeting': meeting,
        'running_optimization': bool(meeting.optimization_task_id),
        'readonly': bool(meeting.optimization_task_id) or not meeting.started is None,
        'score': _eval_timetable(meeting.metrics),
    })

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def optimize_timetable(request, meeting_pk=None, algorithm=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if not meeting.optimization_task_id:
        meeting.optimization_task_id = "xxx:fake"
        meeting.save()
        retval = optimize_timetable_task.apply_async(kwargs={'meeting_id': meeting.id, 'algorithm': algorithm})
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def optimize_timetable_long(request, meeting_pk=None, algorithm=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if not meeting.optimization_task_id:
        meeting.optimization_task_id = "xxx:fake"
        meeting.save()
        retval = optimize_timetable_task.apply_async(kwargs={'meeting_id': meeting.id, 'algorithm': algorithm, 'algorithm_parameters': {
            'population_size': 400,
            'iterations': 2000,
        }})
    return HttpResponseRedirect(reverse('ecs.meetings.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def edit_user_constraints(request, meeting_pk=None, user_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    user = get_object_or_404(User, pk=user_pk)
    formset = UserConstraintFormSet(request.POST or None, prefix='constraint', queryset=user.meeting_constraints.filter(meeting=meeting))
    saved = False
    if formset.is_valid():
        for constraint in formset.save(commit=False):
            constraint.meeting = meeting
            constraint.user = user
            constraint.save()
        formset = UserConstraintFormSet(None, prefix='constraint', queryset=user.meeting_constraints.filter(meeting=meeting))
        saved = True
    return render(request, 'meetings/constraints/user_form.html', {
        'meeting': meeting,
        'participant': user,
        'formset': formset,
        'saved': saved,
    })

@readonly(methods=['GET'])
@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant_quickjump(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = None
    q = request.REQUEST.get('q', '').upper()
    explict_top = 'TOP' in q
    q = q.replace('TOP', '').strip()

    # if we don't explicitly look for a TOP, try an exact ec_number lookup
    if not explict_top:
        tops = meeting.timetable_entries.filter(submission__ec_number__endswith=q).order_by('timetable_index')
        if len(tops) == 1:
            top = tops[0]
    # if we found no TOP yet, try an exact TOP index lookup
    if not top:
        try:
            top = meeting.timetable_entries.get(timetable_index=int(q)-1)
        except (ValueError, TimetableEntry.DoesNotExist):
            pass
    # if we found no TOP yet and don't explicitly look for a TOP, try a fuzzy ec_number lookup
    if not top and not explict_top:
        tops = meeting.timetable_entries.filter(submission__ec_number__icontains=q).order_by('timetable_index')
        if len(tops) == 1:
            top = tops[0]
    if top:
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': top.pk}))

    return render(request, 'meetings/assistant/quickjump_error.html', {
        'meeting': meeting,
        'tops': tops,
    })

@readonly()
@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if meeting.started:
        if meeting.ended:
            return render(request, 'meetings/assistant/error.html', {
                'active': 'assistant',
                'meeting': meeting,
                'message': _(u'This meeting has ended.'),
            })
        try:
            top_pk = request.session.get('meetings:%s:assistant:top_pk' % meeting.pk, None) or meeting[0].pk
            return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': top_pk}))
        except IndexError:
            return render(request, 'meetings/assistant/error.html', {
                'active': 'assistant',
                'meeting': meeting,
                'message': _(u'No TOPs are assigned to this meeting.'),
            })
    else:
        return render(request, 'meetings/assistant/error.html', {
            'active': 'assistant',
            'meeting': meeting,
            'message': _('This meeting has not yet started.'),
        })

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant_start(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    meeting.started = datetime.now()
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant_stop(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    if meeting.open_tops.exists():
        raise Http404(_("unfinished meetings cannot be stopped"))
    meeting.ended = datetime.now()
    meeting.save()
    for vote in Vote.objects.filter(top__meeting=meeting):
        vote.save() # trigger post_save for all votes

    for top in meeting.additional_entries.exclude(pk__in=Vote.objects.exclude(top=None).values('top__pk').query):
        submission = top.submission
        vote = Vote.objects.create(top=top, result='3a')

    for vote in Vote.objects.filter(top__meeting=meeting, submission_form__isnull=False).recessed():
        submission = vote.get_submission()
        submission.schedule_to_meeting()
        if not submission.workflow_lane == SUBMISSION_LANE_BOARD:
            with sudo():
                tasks = Task.objects.for_submission(submission).filter(task_type__workflow_node__uid='categorization_review', deleted_at__isnull=True)
                if tasks and not [t for t in tasks if not t.closed_at]:
                    tasks[0].reopen()
    
    on_meeting_end.send(Meeting, meeting=meeting)
    
    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant_comments(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    form = MeetingAssistantForm(request.POST or None, instance=meeting)
    if form.is_valid():
        form.save()
        if request.POST.get('autosave', False):
            return HttpResponse('OK')
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/assistant/comments.html', {
        'meeting': meeting,
        'form': form,
    })

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant_retrospective_thesis_expedited(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    thesis_vote_formset = ExpeditedVoteFormSet(request.POST or None, queryset=meeting.retrospective_thesis_entries, prefix='thesis')
    expedited_vote_formset = ExpeditedVoteFormSet(request.POST or None, queryset=meeting.expedited_entries, prefix='expedited')
    localec_vote_formset = ExpeditedVoteFormSet(request.POST or None, queryset=meeting.localec_entries, prefix='localec')

    if request.method == 'POST':
        if thesis_vote_formset.is_valid():
            thesis_vote_formset.save()
            thesis_vote_formset = ExpeditedVoteFormSet(None, queryset=meeting.retrospective_thesis_entries, prefix='thesis')
        if expedited_vote_formset.is_valid():
            expedited_vote_formset.save()
            expedited_vote_formset = ExpeditedVoteFormSet(None, queryset=meeting.expedited_entries, prefix='expedited')
        if localec_vote_formset.is_valid():
            localec_vote_formset.save()
            localec_vote_formset = ExpeditedVoteFormSet(None, queryset=meeting.localec_entries, prefix='localec')

    return render(request, 'meetings/assistant/retrospective_thesis_expedited.html', {
        'retrospective_thesis_entries': meeting.retrospective_thesis_entries.filter(vote__isnull=False, vote__is_draft=False).order_by('submission__ec_number'),
        'expedited_entries': meeting.expedited_entries.filter(vote__isnull=False, vote__is_draft=False).order_by('submission__ec_number'),
        'localec_entries': meeting.localec_entries.filter(vote__isnull=False, vote__is_draft=False).order_by('submission__ec_number'),
        'meeting': meeting,
        'thesis_vote_formset': thesis_vote_formset,
        'expedited_vote_formset': expedited_vote_formset,
        'localec_vote_formset': localec_vote_formset,
    })

@readonly(methods=['GET'])
@user_flag_required('is_internal')
@user_group_required('EC-Office')
def meeting_assistant_top(request, meeting_pk=None, top_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = get_object_or_404(TimetableEntry, pk=top_pk)
    simple_save = request.POST.get('simple_save', False)
    autosave = request.POST.get('autosave', False)
    vote, form = None, None

    def next_top_redirect():
        if top.next_open:
            next_top = top.next_open
        else:
            try:
                next_top = meeting.open_tops[0]
            except IndexError:
                return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': next_top.pk}))

    if top.submission:
        try:
            vote = top.vote
        except Vote.DoesNotExist:
            pass
        if simple_save:
            form_cls = SaveVoteForm
        else:
            form_cls = VoteForm
        if top.is_open:
            form = form_cls(request.POST or None, instance=vote)
        else:
            form = form_cls(None, instance=vote, readonly=True)
        if top.is_open and form.is_valid():
            vote = form.save(top)
            if autosave:
                return HttpResponse('OK')
            if form.cleaned_data['close_top']:
                top.is_open = False
                top.save()
            if vote.is_recessed:
                top.submission.schedule_to_meeting()
            return next_top_redirect()
    elif request.method == 'POST':
        top.is_open = False
        top.save()
        return next_top_redirect()

    last_top_cache_key = 'meetings:%s:assistant:top_pk' % meeting.pk
    last_top = None
    if last_top_cache_key in request.session:
        last_top = TimetableEntry.objects.get(pk=request.session[last_top_cache_key])
    request.session[last_top_cache_key] = top.pk

    checklist_review_states = SortedDict()
    blueprint_ct = ContentType.objects.get_for_model(ChecklistBlueprint)
    checklist_ct = ContentType.objects.get_for_model(Checklist)
    if top.submission:
        for blueprint in ChecklistBlueprint.objects.order_by('name'):
            with sudo():
                tasks = Task.objects.for_submission(top.submission).filter(deleted_at=None)
                tasks = tasks.filter(task_type__workflow_node__data_ct=blueprint_ct, task_type__workflow_node__data_id=blueprint.id
                    ) | tasks.filter(content_type=checklist_ct, data_id__in=Checklist.objects.filter(blueprint=blueprint)).exclude(workflow_token__node__uid='external_review_review')
                tasks = list(tasks.order_by('-created_at'))
            checklists = []
            for task in tasks:
                lookup_kwargs = {'blueprint': blueprint}
                if blueprint.multiple:
                    lookup_kwargs['user'] = task.assigned_to
                try:
                    checklist = top.submission.checklists.exclude(status='dropped').get(**lookup_kwargs)
                except Checklist.DoesNotExist:
                    checklist = None
                if not checklist in [x[1] for x in checklists]:
                    checklists.append((task, checklist))
            checklists.reverse()
            checklist_review_states[blueprint] = checklists

    return render(request, 'meetings/assistant/top.html', {
        'meeting': meeting,
        'submission': top.submission,
        'top': top,
        'vote': vote,
        'form': form,
        'last_top': last_top,
        'checklist_review_states': checklist_review_states.items(),
    })

@readonly()
@user_flag_required('is_internal', 'is_resident_member', 'is_board_member')
def agenda_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '%s-%s-%s.pdf' % (
        slugify(meeting.title), meeting.start.strftime('%d-%m-%Y'), slugify(_('agenda'))
    )
    pdf = meeting.get_agenda_pdf(request)
    return pdf_response(pdf, filename=filename)


#@readonly()
@user_group_required('EC-Office')
def send_agenda_to_board(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    agenda_pdf = meeting.get_agenda_pdf(request)
    agenda_filename = '%s-%s-%s.pdf' % (slugify(meeting.title), meeting.start.strftime('%d-%m-%Y'), slugify(_('agenda')))
    timetable_pdf = meeting.get_timetable_pdf(request)
    timetable_filename = '%s-%s-%s.pdf' % (slugify(meeting.title), meeting.start.strftime('%d-%m-%Y'), slugify(_('time slot')))
    attachments = ((agenda_filename, agenda_pdf, 'application/pdf'), (timetable_filename, timetable_pdf, 'application/pdf'))
    subject = _(u'EC Meeting %s') % (meeting.start.strftime('%d.%m.%Y'),)

    users = User.objects.filter(meeting_participations__entry__meeting=meeting).distinct()
    for user in users:
        timeframe = meeting._get_timeframe_for_user(user)
        if timeframe is None:
            continue
        start, end = timeframe
        time = u'{0}–{1}'.format(start.strftime('%H:%M'), end.strftime('%H:%M'))
        htmlmail = unicode(render_html(request, 'meetings/messages/boardmember_invitation.html', {'meeting': meeting, 'time': time, 'recipient': user}))
        deliver(user.email, subject=subject, message=None, message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL, attachments=attachments)

    for user in User.objects.filter(groups__name__in=settings.ECS_MEETING_AGENDA_RECEIVER_GROUPS):
        start, end = meeting.start, meeting.end
        htmlmail = unicode(render_html(request, 'meetings/messages/resident_boardmember_invitation.html', {'meeting': meeting, 'recipient': user}))
        deliver(user.email, subject=subject, message=None, message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL, attachments=attachments)

    tops_with_primary_investigator = meeting.timetable_entries.filter(submission__invite_primary_investigator_to_meeting=True, submission__current_submission_form__primary_investigator__user__isnull=False, timetable_index__isnull=False)
    for top in tops_with_primary_investigator:
        sf = top.submission.current_submission_form
        for u in set([sf.primary_investigator.user, sf.presenter, sf.submitter, sf.sponsor]):
            send_system_message_template(u, subject, 'meetings/messages/primary_investigator_invitation.txt' , {'top': top}, submission=top.submission)

    meeting.agenda_sent_at = datetime.now()
    meeting.save()
    
    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_details', kwargs={'meeting_pk': meeting.pk}))

@readonly(methods=['GET'])
@user_group_required('EC-Office')
def send_expedited_reviewer_invitations(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    form = ExpeditedReviewerInvitationForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        submission_ct = ContentType.objects.get_for_model(Submission)
        categories = ExpeditedReviewCategory.objects.filter(submissions__in=meeting.submissions.all())
        users = User.objects.filter(groups__name='Expedited Review Group', expedited_review_categories__pk__in=categories.values('pk').query)
        start = form.cleaned_data['start']
        for user in users:
            subject = _('Expedited Meeting at {0}').format(start.strftime('%d.%m.%Y'))
            send_system_message_template(user, subject, 'meetings/messages/expedited_reviewer_invitation.txt', {'start': start})
        form = ExpeditedReviewerInvitationForm(None)

        meeting.expedited_reviewer_invitation_sent_for = datetime.now()
        meeting.save()

    return render(request, 'meetings/expedited_reviewer_invitation.html', {
        'form': form,
        'meeting': meeting,
    })

@readonly()
@user_group_required('EC-Office')
def send_protocol(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    protocol_pdf = meeting.get_protocol_pdf(request)
    protocol_filename = '%s-%s-protocol.pdf' % (slugify(meeting.title), meeting.start.strftime('%d-%m-%Y'))
    attachments = ((protocol_filename, protocol_pdf, 'application/pdf'),)
    
    def _send_to(user):
        htmlmail = unicode(render_html(request, 'meetings/messages/protocol.html', {'meeting': meeting, 'recipient': user}))
        deliver(user.email, subject=_('Meeting Protocol'), message=None, message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL, attachments=attachments)

    for user in User.objects.filter(meeting_participations__entry__meeting=meeting).distinct():
        _send_to(user)

    for user in User.objects.filter(groups__name__in=settings.ECS_MEETING_PROTOCOL_RECEIVER_GROUPS):
        _send_to(user)

    tops_with_primary_investigator = meeting.timetable_entries.filter(submission__invite_primary_investigator_to_meeting=True, submission__current_submission_form__primary_investigator__user__isnull=False)
    for top in tops_with_primary_investigator:
        _send_to(top.submission.primary_investigator.user)

    return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_details', kwargs={'meeting_pk': meeting.pk}))


@readonly()
@user_flag_required('is_internal', 'is_resident_member', 'is_board_member')
def protocol_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '%s-%s-protocol.pdf' % (slugify(meeting.title), meeting.start.strftime('%d-%m-%Y'))
    with sudo():
        pdf = meeting.get_protocol_pdf(request)
    return pdf_response(pdf, filename=filename)


@readonly()
@user_flag_required('is_internal', 'is_resident_member', 'is_board_member')
def timetable_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '%s-%s-%s.pdf' % (
        slugify(meeting.title), meeting.start.strftime('%d-%m-%Y'), slugify(_('time slot'))
    )
    with sudo():
        pdf = meeting.get_timetable_pdf(request)
    return pdf_response(pdf, filename=filename)

@readonly()
@user_flag_required('is_internal')
def timetable_htmlemailpart(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    response = render(request, 'meetings/email/timetable.html', {
        'meeting': meeting,
    })
    return response

@readonly()
@user_flag_required('is_internal', 'is_resident_member', 'is_board_member')
def next(request):
    try:
        meeting = Meeting.objects.next()
    except Meeting.DoesNotExist:
        return HttpResponseRedirect(reverse('ecs.dashboard.views.view_dashboard'))
    else:
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_details', kwargs={'meeting_pk': meeting.pk}))


@readonly(methods=['GET'])
@user_flag_required('is_internal', 'is_resident_member', 'is_board_member')
def meeting_details(request, meeting_pk=None, active=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    expert_formset = AssignedMedicalCategoryFormSet(request.POST or None, prefix='experts', queryset=AssignedMedicalCategory.objects.filter(meeting=meeting).distinct())
    experts_saved = False

    if request.method == 'POST' and expert_formset.is_valid() and request.user.ecs_profile.is_internal:
        submitted_form = request.POST.get('submitted_form')
        if submitted_form == 'expert_formset' and expert_formset.is_valid():
            active = 'experts'
            experts_saved = True
            for amc in expert_formset.save(commit=False):
                previous_expert = AssignedMedicalCategory.objects.get(pk=amc.pk).board_member
                amc.save()
                if previous_expert == amc.board_member:
                    continue
                entries = list(meeting.timetable_entries.filter(submission__medical_categories=amc.category).distinct())
                if previous_expert:
                    # remove all participations for a previous selected board member.
                    # XXX: this may delete manually entered data. (FMD2)
                    Participation.objects.filter(medical_category=amc.category, entry__meeting=meeting, user=previous_expert).delete()

                    # delete obsolete board member review tasks
                    for entry in entries:
                        with sudo():
                            tasks = Task.objects.for_data(entry.submission).filter(
                                task_type__workflow_node__uid='board_member_review', closed_at=None, deleted_at__isnull=True, assigned_to=previous_expert)
                            tasks.mark_deleted()
                if amc.board_member:
                    meeting.create_boardmember_reviews()

    tops = meeting.timetable_entries.all()
    votes_list = []
    all_votes = list(Vote.objects.filter(top__meeting=meeting))
    for top in tops:
        votes = [v for v in all_votes if v.top == top]
        if not votes:
            vote = None
        else:
            vote = votes[0]
        votes_list.append({'top_index': top.index, 'top': str(top), 'vote': vote})
    
    submissions = meeting.submissions.order_by('ec_number')

    return render(request, 'meetings/details.html', {
        'cumulative_count': submissions.distinct().count(),

        'board_submissions': submissions.for_board_lane(),
        'amg_submissions': submissions.for_board_lane().amg().exclude(pk__in=meeting.submissions.mpg().values('pk').query),
        'mpg_submissions': submissions.for_board_lane().mpg().exclude(pk__in=meeting.submissions.amg().values('pk').query),
        'amg_mpg_submissions': submissions.for_board_lane().amg_mpg(),
        'not_amg_and_not_mpg_submissions': submissions.for_board_lane().not_amg_and_not_mpg(),

        'retrospective_thesis_submissions': submissions.for_thesis_lane(),
        'expedited_submissions': submissions.expedited(),
        'localec_submissions': submissions.localec(),

        'dissertation_submissions': submissions.filter(current_submission_form__project_type_education_context=1),
        'diploma_thesis_submissions': submissions.filter(current_submission_form__project_type_education_context=2),
        'amg_multi_main_submissions': submissions.amg().filter(current_submission_form__submission_type=SUBMISSION_TYPE_MULTICENTRIC),
        'billable_submissions': submissions.exclude(remission=True),
        'b3_examined_submissions': submissions.filter(pk__in=Vote.objects.filter(result='3b').values('submission_form__submission').query),
        'b3_not_examined_submissions': submissions.filter(pk__in=Vote.objects.filter(result='3a').values('submission_form__submission').query),

        'meeting': meeting,
        'expert_formset': expert_formset,
        'experts_saved': experts_saved,
        'votes_list': votes_list,
        'active': active,
    })

@user_flag_required('is_internal')
@user_group_required('EC-Office')
def edit_meeting(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    form = MeetingForm(request.POST or None, instance=meeting)
    if form.is_valid():
        meeting = form.save()
        return HttpResponseRedirect(reverse('ecs.meetings.views.meeting_details', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/form.html', {
        'form': form,
        'meeting': meeting,
    })
