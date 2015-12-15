# -*- coding: utf-8 -*-
from datetime import timedelta

from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.utils import timezone

from celery.task import periodic_task
from celery.schedules import crontab

from ecs.votes.models import Vote
from ecs.core.models.constants import SUBMISSION_LANE_LOCALEC
from ecs.utils.common_messages import send_submission_message
from ecs.users.utils import get_office_user


def send_vote_expired(vote):
    recipients = vote.submission_form.get_presenting_parties().get_users()
    recipients.add(get_office_user())
    submission = vote.get_submission()

    url = reverse('readonly_submission_form', kwargs={ 'submission_form_pk': vote.submission_form.pk })
    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at
    text = _(u'Das Votum für die Studie EK-Nr. %(ec_number)s vom %(vote_date)s ist abgelaufen.\n') % {
        'url': url,
        'ec_number': submission.get_ec_number_display(),
        'vote_date': vote_date.strftime('%d.%m.%Y'),
    }

    subject = _(u'Ablauf des Votums für die Studie EK-Nr. %s') % submission.get_ec_number_display()
    send_submission_message(submission, subject, text, recipients)

def send_vote_reminder_submitter(vote):
    recipients = vote.submission_form.get_presenting_parties().get_users()
    submission = vote.get_submission()

    url = reverse('readonly_submission_form', kwargs={ 'submission_form_pk': vote.submission_form.pk })
    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at
    text = _(u'''Das Votum für die Studie EK-Nr. %(ec_number)s vom %(vote_date)s läuft in drei Wochen ab.
Stellen Sei bitte zeitgerecht den Antrag auf Verlängerung des Votums.
Steigen Sie dazu ins ECS ein, gehen Sie im Seitenmenü rechts auf „Studien Meldungen“ > „Neue Meldung“,
wählen Sie dann „Verlängerung der Gültigkeit des Votums“ und machen Sie die erforderlichen Angaben.

Achtung: Sollte es sich bei Ihrer Studie um eine multizentrische Arzneimittelprüfung handeln,
bei der die Ethikkommission der MedUni Wien  nicht als Leit-Ethikkommission,
sondern als lokale Ethikkommission fungiert, dann können Sie diese Aufforderung ignorieren.
In solchen Fällen ist die Leit-Ethikkommission für die Votumsverlängerung zuständig.

Mit freundlichen Grüßen,

das Team der Ethik-Kommission
    ''') % {
        'url': url,
        'ec_number': submission.get_ec_number_display(),
        'vote_date': vote_date.strftime('%d.%m.%Y'),
    }

    subject = _(u'Ablauf des Votums für die Studie EK-Nr. %s') % submission.get_ec_number_display()
    send_submission_message(submission, subject, text, recipients)
    
def send_vote_reminder_office(vote):
    recipients = [get_office_user()]
    submission = vote.get_submission()

    url = reverse('readonly_submission_form', kwargs={ 'submission_form_pk': vote.submission_form.pk })
    if vote.top:
        vote_date = vote.top.meeting.start
    else:
        vote_date = vote.published_at
    text = _(u'Das Votum für die Studie EK-Nr. %(ec_number)s vom %(vote_date)s läuft in einer Woche ab.\n') % {
        'url': url,
        'ec_number': submission.get_ec_number_display(),
        'vote_date': vote_date.strftime('%d.%m.%Y'),
    }

    subject = _(u'Ablauf des Votums für die Studie EK-Nr. %s') % submission.get_ec_number_display()
    send_submission_message(submission, subject, text, recipients)


@periodic_task(run_every=timedelta(days=1))
def send_reminder_messages(today=None):
    if today is None:
        today = timezone.now().date()

    votes = (Vote.objects
        .filter(result='1', published_at__isnull=False, valid_until__isnull=False)
        .exclude(submission_form__submission__workflow_lane=SUBMISSION_LANE_LOCALEC)
        .exclude(submission_form__submission__is_finished=True))
    
    for vote in votes:
        valid_until = vote.valid_until.date()
        if today < valid_until:
            days_valid = (valid_until - today).days
        else:
            days_valid = 0 - (today - valid_until).days

        if days_valid == 21:
            send_vote_reminder_submitter(vote)
        elif days_valid == 7:
            send_vote_reminder_office(vote)
        elif days_valid == -1:
            send_vote_expired(vote)


@periodic_task(run_every=crontab(hour=3, minute=58))
def expire_votes():
    for vote in Vote.objects.filter(valid_until__lt=timezone.now(), is_expired=False):
        vote.expire()
