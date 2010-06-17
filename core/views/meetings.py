import datetime
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.utils import simplejson
from django.contrib.auth.models import User
from django.utils.datastructures import SortedDict
from django.db.models import Count
from ecs.core.views.utils import render
from ecs.core.models import Meeting, Participation, TimetableEntry, Submission, MedicalCategory, Participation, Vote, ChecklistBlueprint
from ecs.core.forms.meetings import MeetingForm, TimetableEntryForm, UserConstraintFormSet, SubmissionSchedulingForm
from ecs.core.forms.voting import VoteForm, SaveVoteForm
from ecs.core.task_queue import optimize_timetable_task
from ecs.utils.timedelta import parse_timedelta


def create_meeting(request):
    form = MeetingForm(request.POST or None)
    if form.is_valid():
        meeting = form.save()
        return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'meetings/form.html', {
        'form': form,
    })
    
def meeting_list(request):
    return render(request, 'meetings/list.html', {
        #.filter(start__gte=datetime.datetime.now())
        'meetings': Meeting.objects.order_by('start')
    })
    
def schedule_submission(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    form = SubmissionSchedulingForm(request.POST or None)
    if form.is_valid():
        kwargs = form.cleaned_data.copy()
        meeting = kwargs.pop('meeting')
        timetable_entry = meeting.add_entry(submission=submission, duration=datetime.timedelta(minutes=7.5), **kwargs)
        return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    return render(request, 'submissions/schedule.html', {
        'submission': submission,
        'form': form,
    })

def add_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    is_break = request.GET.get('break', False)
    if is_break:
        entry = meeting.add_break(duration=datetime.timedelta(minutes=30))
    else:
        entry = meeting.add_entry(duration=datetime.timedelta(minutes=7, seconds=30), submission=Submission.objects.order_by('?')[:1].get())
        import random
        for user in User.objects.order_by('?')[:random.randint(1, 4)]:
            Participation.objects.create(entry=entry, user=user)
    return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def remove_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    entry = get_object_or_404(TimetableEntry, pk=entry_pk)
    entry.delete()
    return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def update_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    entry = get_object_or_404(TimetableEntry, pk=entry_pk)
    form = TimetableEntryForm(request.POST)
    if form.is_valid():
        duration = form.cleaned_data['duration']
        if duration:
            entry.duration = parse_timedelta(duration)
        entry.optimal_start = form.cleaned_data['optimal_start']
        entry.save()
    return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def move_timetable_entry(request, meeting_pk=None):
    from_index = int(request.GET.get('from_index'))
    to_index = int(request.GET.get('to_index'))
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    meeting[from_index].index = to_index
    return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))
    
def users_by_medical_category(request):
    category = get_object_or_404(MedicalCategory, pk=request.POST.get('category'))
    users = list(User.objects.filter(medical_categories=category, ecs_profile__board_member=True).values('pk', 'username'))
    return HttpResponse(simplejson.dumps(users), content_type='text/json')

def timetable_editor(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    return render(request, 'meetings/timetable/editor.html', {
        'meeting': meeting,
        'running_optimization': bool(meeting.optimization_task_id),
    })
    
def participation_editor(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    users = User.objects.all()
    entries = meeting.timetable_entries.exclude(submission=None).select_related('submission')
    if request.method == 'POST':
        for entry in entries:
            for cat in entry.medical_categories:
                participations = Participation.objects.filter(entry=entry, medical_category=cat)
                user_pks = set(map(int, request.POST.getlist('users_%s_%s' % (entry.pk, cat.pk))))
                participations.exclude(user__pk__in=user_pks).delete()
                for user in User.objects.filter(pk__in=user_pks).exclude(meeting_participations__in=participations.values('pk')):
                    entry.add_user(user, cat)
            
    return render(request, 'meetings/timetable/participation_editor.html', {
        'meeting': meeting,
        'categories': MedicalCategory.objects.all(),
    })

def optimize_timetable(request, meeting_pk=None, algorithm=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if not meeting.optimization_task_id:
        retval = optimize_timetable_task.delay(meeting_id=meeting.id,algorithm=algorithm)
        meeting.optimization_task_id = retval.task_id
        meeting.save()
    return HttpResponseRedirect(reverse('ecs.core.views.timetable_editor', kwargs={'meeting_pk': meeting.pk}))

def edit_user_constraints(request, meeting_pk=None, user_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    user = get_object_or_404(User, pk=user_pk)
    constraint_formset = UserConstraintFormSet(request.POST or None, prefix='constraint', queryset=user.meeting_constraints.all())
    if constraint_formset.is_valid():
        for constraint in constraint_formset.save(commit=False):
            constraint.meeting = meeting
            constraint.user = user
            constraint.save()
        return HttpResponseRedirect(reverse('ecs.core.views.meetings.edit_user_constraints', kwargs={'meeting_pk': meeting.pk, 'user_pk': user.pk}))
    return render(request, 'meetings/constraints/user_form.html', {
        'meeting': meeting,
        'participant': user,
        'constraint_formset': constraint_formset,
    })
    
def meeting_assistant_quickjump(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = None
    q = request.REQUEST.get('q', '').upper()
    explict_top = 'TOP' in q
    q = q.replace('TOP', '').strip()
    
    # if we don't explicitly look for a TOP, try an exact ec_number lookup
    if not explict_top:
        tops = meeting.timetable_entries.filter(submission__ec_number__iexact=q).order_by('timetable_index')
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
        return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': top.pk}))
    
    return render(request, 'meetings/assistant/quickjump_error.html', {
        'meeting': meeting,
        'tops': tops,
    })
    
def meeting_assistant(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if meeting.started:
        if meeting.ended:
            return render(request, 'meetings/assistant/error.html', {
                'meeting': meeting,
                'message': 'Diese Sitzung wurde beendet.',
            })
        try:
            top_pk = request.session.get('meetings:%s:assistant:top_pk' % meeting.pk, None) or meeting[0].pk
            return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': top_pk}))
        except IndexError:
            return render(request, 'meetings/assistant/error.html', {
                'meeting': meeting,
                'message': 'Dieser Sitzung sind keine TOPs zugeordnet.',
            })
    else:
        return render(request, 'meetings/assistant/error.html', {
            'meeting': meeting,
            'message': 'Dieses Sitzung wurde noch nicht begonnen.',
        })
        
def meeting_assistant_start(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    meeting.started = datetime.datetime.now()
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
    
def meeting_assistant_stop(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    if meeting.open_tops.count():
        raise Http404("unfinished meetings cannot be stopped")
    meeting.ended = datetime.datetime.now()
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))

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
                return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))
        return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant_top', kwargs={'meeting_pk': meeting.pk, 'top_pk': next_top.pk}))
    
    if top.submission:
        try:
            vote = top.vote
        except Vote.DoesNotExist:
            pass
        if simple_save:
            form_cls = SaveVoteForm
        else:
            form_cls = VoteForm
        form = form_cls(request.POST or None, instance=vote)
        print autosave, form.is_valid()
        if form.is_valid():
            vote = form.save(commit=False)
            vote.top = top
            vote.save()
            if autosave:
                return HttpResponse('OK')
            if form.cleaned_data['close_top']:
                top.is_open = False
                top.save()
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
    if top.submission:
        for blueprint in ChecklistBlueprint.objects.order_by('name'):
            checklist_review_states[blueprint] = None
        for checklist in top.submission.checklists.select_related('blueprint'):
            checklist_review_states[checklist.blueprint] = checklist

    return render(request, 'meetings/assistant/top.html', {
        'meeting': meeting,
        'submission': top.submission,
        'top': top,
        'vote': vote,
        'form': form,
        'last_top': last_top,
        'checklist_review_states': checklist_review_states.items(),
    })

def meeting_assistant_clear(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    Vote.objects.filter(top__meeting=meeting).delete()
    meeting.timetable_entries.update(is_open=True)
    meeting.started = None
    meeting.ended = None
    meeting.save()
    return HttpResponseRedirect(reverse('ecs.core.views.meeting_assistant', kwargs={'meeting_pk': meeting.pk}))