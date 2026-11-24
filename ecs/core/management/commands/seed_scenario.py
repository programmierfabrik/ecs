import json

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ecs.core.models import SubmissionForm
from ecs.users.utils import sudo
from ecs.utils import factories

STAGES = ('scheduled', 'started', 'voted', 'ended', 'published')


class Command(BaseCommand):
    help = ('Take a new study through the real meeting/vote lifecycle (mails go to the '
            'configured SMTP, e.g. Mailpit). Development only.')

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='scenario', required=True)
        study = sub.add_parser('study', help='a submission form, voted on in one meeting per --votes entry')
        study.add_argument('--set', dest='fields', action='append', default=[], metavar='FIELD=VALUE',
                           help='submission form field, value as JSON or plain text, '
                                'e.g. project_type_medical_device=true (repeatable)')
        study.add_argument('--votes', nargs='*', default=['1'], metavar='RESULT',
                           help="vote result per meeting, in order, e.g. 3b 1 (default: 1)")
        study.add_argument('--until', choices=STAGES, default='published',
                           help='how far the last meeting goes (default: published)')
        study.add_argument('--participants', nargs='*', default=[], metavar='EMAIL',
                           help='users taking part in each TOP')
        study.add_argument('--board-members', nargs='*', default=[], metavar='EMAIL',
                           help='EK members selected for each new meeting')
        study.add_argument('--protocol', action='store_true',
                           help='render the protocol of each ended meeting')

    def handle(self, scenario, **options):
        if not settings.DEBUG:
            raise CommandError('seed_scenario only runs with DEBUG=True')
        try:
            with sudo(), transaction.atomic():
                getattr(self, 'seed_' + scenario)(**options)
        except ValueError as e:
            raise CommandError(str(e)) from e

    def seed_study(self, fields, votes, until, participants, board_members, protocol, **options):
        sf = factories.create_submission_form(**self._fields(fields))
        participants, board_members = self._users(participants), self._users(board_members)
        self.stdout.write(f'submission={sf.submission_id} ec_number={sf.submission.ec_number} submission_form={sf.pk}')
        for i, result in enumerate(votes):
            last = i == len(votes) - 1
            stop = STAGES.index(until) if last else len(STAGES) - 1
            # the first meeting is ours; after that the study goes wherever the
            # previous vote sent it (a recessed vote reschedules it on publication)
            meeting = factories.create_meeting() if i == 0 else None
            top = factories.schedule(sf.submission, meeting, participants=participants)
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

    def _fields(self, assignments):
        fields = {}
        for assignment in assignments:
            name, sep, raw = assignment.partition('=')
            if not sep:
                raise CommandError(f'--set needs FIELD=VALUE, got {assignment!r}')
            try:
                SubmissionForm._meta.get_field(name)
            except FieldDoesNotExist:
                raise CommandError(f'unknown submission form field {name!r}') from None
            try:
                fields[name] = json.loads(raw)
            except ValueError:
                fields[name] = raw
        return fields

    def _users(self, emails):
        users = list(User.objects.filter(email__in=emails))
        missing = set(emails) - {u.email for u in users}
        if missing:
            raise CommandError(f'unknown users: {", ".join(sorted(missing))}')
        return users
