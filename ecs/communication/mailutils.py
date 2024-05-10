import html
import re
import textwrap

import pytz
from django.conf import settings
from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives, make_msgid
from django.utils.html import strip_tags


def html2text(htmltext):
    text = html.unescape(strip_tags(htmltext))
    text = '\n\n'.join(re.split(r'\s*\n\s*\n\s*', text))
    text = re.sub('\s\s\s+', ' ', text)
    wrapper = textwrap.TextWrapper(
        replace_whitespace=False, drop_whitespace=False, width=72)
    return '\n'.join(wrapper.wrap(text))


def create_mail(subject, message, from_email, recipient, message_html=None,
                attachments=None, rfc2822_headers=None):

    from ecs.core.models import AdvancedSettings

    headers = {'Message-ID': make_msgid(domain=settings.DOMAIN)}
    if from_email == settings.DEFAULT_FROM_EMAIL:
        # if empty, set Auto-Submitted and Reply-To for mails from DEFAULT_FROM_EMAIL
        if not rfc2822_headers or not rfc2822_headers.get('Auto-Submitted', None):
            headers.update({'Auto-Submitted': 'auto-generated'})
        if not rfc2822_headers or not rfc2822_headers.get('Reply-To', None):
            headers.update({'Reply-To': AdvancedSettings.objects.get(pk=1).default_contact.email})

    if rfc2822_headers:
        headers.update(rfc2822_headers)

    if message is None:  # make text version out of html if text version is missing
        message = html2text(message_html)

    if message_html:
        msg = EmailMultiAlternatives(subject, message, from_email, [recipient], headers=headers)
        msg.attach_alternative(message_html, "text/html")
    else:
        msg = EmailMessage(subject, message, from_email, [recipient], headers=headers)

    if attachments:
        for filename, content, mimetype in attachments:
            msg.attach(filename, content, mimetype)

    return msg


def deliver(recipient_list, *args, **kwargs):
    '''
    send email to recipient list
    returns a list of (msgid, rawmessage) for each messages to be sent
    '''
    # make a list if only one recipient (and therefore string) is there
    if isinstance(recipient_list, str):
        recipient_list = [recipient_list]

    sentids = []
    for recipient in recipient_list:
        sentids.append(deliver_to_recipient(recipient, *args, **kwargs))

    return sentids


def deliver_to_recipient(recipient, subject, message, from_email,
    message_html=None, attachments=None, nofilter=False, rfc2822_headers=None, force_send=False):

    msg = create_mail(subject, message, from_email, recipient,
                      message_html, attachments, rfc2822_headers)
    msgid = msg.extra_headers['Message-ID']

    if not settings.ECS_DISABLE_EMAIL_DELIVERY or force_send:
        connection = mail.get_connection()
        connection.send_messages([msg])

    return (msgid, msg.message(),)


def generate_ics_file(user_email, event_name, event_description, location, start_datetime, end_datetime):
    proid = f"Ethic Committee System {settings.ECS_VERSION}"
    vienna_timezone = pytz.timezone('Europe/Vienna')

    dt_format = '%Y%m%dT%H%M%S'
    start_datetime_formatted = start_datetime.astimezone(vienna_timezone).strftime(dt_format)
    end_datetime_formatted = end_datetime.astimezone(vienna_timezone).strftime(dt_format)

    ics_content = f"BEGIN:VCALENDAR\n" \
                  f"VERSION:2.0\n" \
                  f"PRODID:-//{proid}//EN\n" \
                  f"BEGIN:VEVENT\n" \
                  f"UID:{user_email}\n" \
                  f"SUMMARY:{event_name}\n" \
                  f"DESCRIPTION:{event_description}\n" \
                  f"LOCATION:{location}\n" \
                  f"DTSTAMP:{start_datetime_formatted}\n" \
                  f"DTSTART:{start_datetime_formatted}\n" \
                  f"DTEND:{end_datetime_formatted}\n" \
                  f"END:VEVENT\n" \
                  f"END:VCALENDAR"

    return bytes(ics_content, 'utf-8')
