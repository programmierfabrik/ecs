import json

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ecs.core.models import Submission, SubmissionForm
from ecs.core.models.constants import (
    SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED, SUBMISSION_LANE_LOCALEC, SUBMISSION_LANE_RETROSPECTIVE_THESIS,
)
from ecs.users.utils import sudo
from ecs.utils import factories
from ecs.votes.models import Vote
from ecs.workflow.models import NODE_TYPE_CATEGORY_ACTIVITY, Node

STAGES = ('scheduled', 'started', 'voted', 'ended', 'published')
LANES = {
    'board': SUBMISSION_LANE_BOARD,
    'expedited': SUBMISSION_LANE_EXPEDITED,
    'thesis': SUBMISSION_LANE_RETROSPECTIVE_THESIS,
    'localec': SUBMISSION_LANE_LOCALEC,
}


class Command(BaseCommand):
    help = ('Take a new study through the real meeting/vote lifecycle (mails go to the '
            'configured SMTP, e.g. Mailpit), or list and do the open tasks of a study. Development only.')

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='scenario', required=True)
        study = sub.add_parser('study', help='a submission form, voted on in one meeting per --votes entry')
        study.add_argument('--set', dest='fields', action='append', default=[], metavar='FIELD=VALUE',
                           help='submission form field, value as JSON or plain text, '
                                'e.g. project_type_medical_device=true (repeatable)')
        study.add_argument('--lane', choices=LANES,
                           help='workflow lane chosen at categorization (default: board, '
                                'or the lane the study type implies)')
        study.add_argument('--votes', nargs='*', default=['1'], metavar='RESULT',
                           help="vote result per meeting, in order, e.g. 3b 1 (default: 1)")
        study.add_argument('--until', default='published', metavar='STAGE|NODE',
                           help=f'how far the last meeting goes: {"|".join(STAGES)} (default: published); '
                                'or a workflow node uid: stop once that task is open (a submission '
                                'node before the first meeting, a vote node after the last one)')
        study.add_argument('--participants', nargs='*', default=[], metavar='EMAIL',
                           help='users taking part in each TOP')
        study.add_argument('--board-members', nargs='*', default=[], metavar='EMAIL',
                           help='EK members selected for each new meeting')
        study.add_argument('--protocol', action='store_true',
                           help='render the protocol of each ended meeting')

        tasks = sub.add_parser('tasks', help='list the open tasks of a submission (its votes and checklists '
                                             'included), or do one')
        tasks.add_argument('submission', type=int, help='submission id')
        tasks.add_argument('--do', metavar='NODE', help='node uid of the open task to do')
        tasks.add_argument('--choice', help='choice as JSON or plain text (default: the first one the page offers)')
        tasks.add_argument('--user', metavar='EMAIL', help='who does it (default: assignee or first group member)')
        tasks.add_argument('--set', dest='fields', action='append', default=[], metavar='FIELD=VALUE',
                           help="field of the task page's form, value as JSON or plain text (repeatable)")

    def handle(self, scenario, **options):
        if not settings.DEBUG:
            raise CommandError('seed_scenario only runs with DEBUG=True')
        try:
            with sudo(), transaction.atomic():
                getattr(self, 'seed_' + scenario)(**options)
        except ValueError as e:
            raise CommandError(str(e)) from e

    def seed_study(self, fields, lane, votes, until, participants, board_members, protocol, **options):
        node_graph = None if until in STAGES else self._node_graph(until)
        fields = self._assignments(fields)
        for name in fields:
            try:
                SubmissionForm._meta.get_field(name)
            except FieldDoesNotExist:
                raise CommandError(f'unknown submission form field {name!r}') from None
        categorization = {'workflow_lane': LANES[lane]} if lane else {}
        participants, board_members = self._users(participants), self._users(board_members)

        sf = factories.create_submission_form(**fields)
        submission = sf.submission
        self.stdout.write(f'submission={submission.pk} ec_number={submission.ec_number} submission_form={sf.pk}')
        if node_graph == 'submission':
            factories.run_workflow(submission, until=until, fields={'categorization': categorization})
            self._write_open(submission)
            return

        for i, result in enumerate(votes):
            last = i == len(votes) - 1
            if not last:
                stop = len(STAGES) - 1
            elif node_graph == 'vote':
                stop = STAGES.index('ended')
            else:
                stop = STAGES.index(until)
            # the first meeting is ours; after that the study goes wherever the
            # previous vote sent it (a recessed vote reschedules it on publication)
            meeting = factories.create_meeting() if i == 0 else None
            top = factories.schedule(submission, meeting, participants=participants, **categorization)
            meeting = top.meeting
            meeting.board_members.add(*board_members)
            line = f'meeting={meeting.pk} top={top.pk}'
            if stop >= STAGES.index('started'):
                factories.start_meeting(meeting)
            if stop >= STAGES.index('voted'):
                vote = factories.record_vote(top, result)
                line += f' vote={vote.pk} result={vote.result}'
            if stop >= STAGES.index('ended'):
                factories.end_meeting(meeting)
                if protocol:
                    meeting.render_protocol_pdf()
            if stop >= STAGES.index('published'):
                factories.finish_vote_workflow(vote)
                line += ' published'
            self.stdout.write(line + f' ({STAGES[stop]})')
        if node_graph == 'vote':
            factories.run_workflow(vote, until=until)
        self._write_open(submission)

    def seed_tasks(self, submission, do, choice, user, fields, **options):
        try:
            submission = Submission.objects.get(pk=submission)
        except Submission.DoesNotExist:
            raise CommandError(f'no submission {submission}') from None
        if do:
            data = next((d for d in self._task_data(submission)
                         if do in factories._node_uids(factories._open_tasks(d))), None)
            if data is None:
                raise CommandError(f'no open {do} task; open: {self._open(submission) or "none"}')
            kwargs = self._assignments(fields)
            if choice is not None:
                kwargs['choice'] = self._value(choice)
            if user:
                kwargs['user'] = self._users([user])[0]
            task = factories.do_task(data, do, **kwargs)
            self.stdout.write(f'done {do} task={task.pk} by {task.assigned_to.email}')
        self._write_open(submission)

    def _task_data(self, submission):
        return [submission, *Vote.objects.filter(submission=submission).order_by('pk'),
                *submission.checklists.order_by('pk')]

    def _open(self, submission):
        return ' '.join(
            f'{uid}({type(data).__name__.lower()}={data.pk})'
            for data in self._task_data(submission)
            for uid in factories._node_uids(factories._open_tasks(data)))

    def _write_open(self, submission):
        self.stdout.write(f'open: {self._open(submission) or "none"}')

    def _node_graph(self, uid):
        graphs = set(Node.objects.filter(uid=uid, node_type__category=NODE_TYPE_CATEGORY_ACTIVITY).values_list('graph__content_type__model', flat=True))
        if not graphs:
            raise CommandError(f'--until: {uid!r} is neither a stage ({", ".join(STAGES)}) nor the uid of a task node')
        if graphs - {'submission', 'vote'}:
            raise CommandError(f'--until: {uid!r} is a {"/".join(sorted(graphs))} node; '
                               'only submission and vote nodes are supported')
        return graphs.pop()

    def _assignments(self, assignments):
        values = {}
        for assignment in assignments:
            name, sep, raw = assignment.partition('=')
            if not sep:
                raise CommandError(f'--set needs FIELD=VALUE, got {assignment!r}')
            values[name] = self._value(raw)
        return values

    def _value(self, raw):
        try:
            return json.loads(raw)
        except ValueError:
            return raw

    def _users(self, emails):
        users = list(User.objects.filter(email__in=emails))
        missing = set(emails) - {u.email for u in users}
        if missing:
            raise CommandError(f'unknown users: {", ".join(sorted(missing))}')
        return users
