from datetime import timedelta

from django.utils.translation import ugettext as _
from django.utils import timezone
from django.db.models import F, Func

from celery.task import periodic_task
from celery.schedules import crontab

from ecs.votes.models import Vote
from ecs.core.models.constants import SUBMISSION_LANE_LOCALEC
from ecs.users.utils import get_user, get_office_user
from ecs.communication.utils import send_message
from ecs.votes.constants import PERMANENT_VOTE_RESULTS


def send_submission_message(submission, subject, text, recipients):
    sender = get_user('root@system.local')
    for recipient in recipients:
        send_message(sender, recipient, subject, text, submission=submission)


def send_vote_expired(vote):
    sf = vote.get_submission().current_submission_form
    recipients = sf.get_presenting_parties().get_users()
    recipients.add(get_office_user())
    submission = vote.get_submission()

    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at
    text = _('Das Votum für die Studie EK-Nr. %(ec_number)s vom %(vote_date)s ist abgelaufen.\n') % {
        'ec_number': submission.get_ec_number_display(),
        'vote_date': vote_date.strftime('%d.%m.%Y'),
    }

    subject = _('Vote for Submission {ec_number} has expired').format(
        ec_number=submission.get_ec_number_display())
    send_submission_message(submission, subject, text, recipients)

def send_vote_reminder_submitter(vote):
    sf = vote.get_submission().current_submission_form
    recipients = sf.get_presenting_parties().get_users()
    submission = vote.get_submission()

    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at
    text = _('''Das Votum für die Studie EK-Nr. %(ec_number)s vom %(vote_date)s läuft in drei Wochen ab.
Stellen Sie bitte zeitgerecht den Antrag auf Verlängerung des Votums.
Steigen Sie dazu ins ECS ein, gehen Sie im Seitenmenü rechts auf „Studien Meldungen“ > „Neue Meldung“,
wählen Sie dann „Verlängerung der Gültigkeit des Votums“ und machen Sie die erforderlichen Angaben.

Achtung: Sollte es sich bei Ihrer Studie um eine multizentrische Arzneimittelprüfung handeln,
bei der die Ethikkommission nicht als Leit-Ethikkommission, sondern als lokale Ethikkommission
fungiert, dann können Sie diese Aufforderung ignorieren. In solchen Fällen ist die
Leit-Ethikkommission für die Votumsverlängerung zuständig.

Mit freundlichen Grüßen,

das Team der Ethik-Kommission
    ''') % {
        'ec_number': submission.get_ec_number_display(),
        'vote_date': vote_date.strftime('%d.%m.%Y'),
    }

    subject = _('Vote for Submission {ec_number} will expire in three weeks').format(
        ec_number=submission.get_ec_number_display())
    send_submission_message(submission, subject, text, recipients)
    
def send_vote_reminder_office(vote):
    recipients = [get_office_user()]
    submission = vote.get_submission()

    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at
    text = _('Das Votum für die Studie EK-Nr. %(ec_number)s vom %(vote_date)s läuft in einer Woche ab.\n') % {
        'ec_number': submission.get_ec_number_display(),
        'vote_date': vote_date.strftime('%d.%m.%Y'),
    }

    subject = _('Vote for Submission {ec_number} will expire in one week').format(
        ec_number=submission.get_ec_number_display())
    send_submission_message(submission, subject, text, recipients)


def send_temporary_vote_reminder_submitter(vote):
    sf = vote.get_submission().current_submission_form
    recipients = sf.get_presenting_parties().get_users()
    submission = vote.get_submission()

    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at

    text = _('''There is still no permanent vote for submission {ec_number}. The current
temporary vote was published on the {vote_date}. Please make sure you've
sent all necessary documents to the ethics commission.

Yours sincerely,

the team of the ethics commission
    ''').format(
        ec_number=submission.get_ec_number_display(),
        vote_date=vote_date.strftime('%d.%m.%Y')
    )

    subject = _('Temporary vote for Submission {ec_number}').format(
        ec_number=submission.get_ec_number_display())
    send_submission_message(submission, subject, text, recipients)


def send_temporary_vote_reminder_office(vote):
    recipients = [get_office_user()]
    submission = vote.get_submission()

    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at

    text = _('''There is still no permanent vote for submission {ec_number}. The current
temporary vote was published on the {vote_date}.
    ''').format(
        ec_number=submission.get_ec_number_display(),
        vote_date=vote_date.strftime('%d.%m.%Y')
    )

    subject = _('Temporary vote for Submission {ec_number}').format(
        ec_number=submission.get_ec_number_display())
    send_submission_message(submission, subject, text, recipients)


@periodic_task(run_every=timedelta(days=1))
def send_reminder_messages(today=None):
    if today is None:
        today = timezone.now().date()


    votes = (Vote.objects
        .filter(published_at__isnull=False, valid_until__isnull=False)
        .exclude(submission_form__submission__workflow_lane=SUBMISSION_LANE_LOCALEC)
        .exclude(submission_form__submission__is_finished=True)
        .annotate(valid_until_date=Func(F('valid_until'), function='DATE')))

    for vote in votes.filter(
            valid_until_date=Func(today + timedelta(days=21), function='DATE')):
        assert vote.result == '1'
        send_vote_reminder_submitter(vote)

    for vote in votes.filter(
            valid_until_date=Func(today + timedelta(days=7), function='DATE')):
        assert vote.result == '1'
        send_vote_reminder_office(vote)

    for vote in votes.filter(
            valid_until_date=Func(today - timedelta(days=1), function='DATE')):
        assert vote.result == '1'
        send_vote_expired(vote)


    tmp_votes = (Vote.objects
        .exclude(result__in=PERMANENT_VOTE_RESULTS)
        .exclude(_currently_published_for=None)
        .annotate(published_date=Func(F('published_at'), function='DATE')))

    for vote in tmp_votes.filter(
            published_date=Func(today - timedelta(days=150), function='DATE')):
        send_temporary_vote_reminder_submitter(vote)

    for vote in tmp_votes.filter(
            published_date=Func(today - timedelta(days=240), function='DATE')):
        send_temporary_vote_reminder_office(vote)


@periodic_task(run_every=crontab(hour=3, minute=58))
def expire_votes():
    now = timezone.now()
    for vote in Vote.objects.filter(valid_until__lt=now, is_expired=False):
        vote.expire()
