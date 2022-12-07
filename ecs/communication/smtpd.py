import base64
import email
import logging
import re
from datetime import timedelta

import chardet
from asgiref.sync import sync_to_async
from django.utils import timezone

from ecs import settings
from ecs.communication.mailutils import html2text
from ecs.communication.models import Message

logger = logging.getLogger(__name__)


def _get_content(message_part):
    payload = message_part.get_payload(decode=True)

    if message_part.get_content_charset() is None:
        charset = chardet.detect(payload)['encoding']
        logger.debug('no content charset declared, detection result: {0}'.format(charset))
    else:
        charset = message_part.get_content_charset()

    if charset in ['iso-8859-8-i', 'iso-8859-8-e']:
        # XXX https://bugs.python.org/issue18624
        logger.debug('aliasing charset iso-8859-8 for {0}'.format(charset))
        charset = 'iso-8859-8'

    logger.debug('message-part: type: {0} charset: {1}'.format(
        message_part.get_content_type(), charset))
    content = str(payload, charset, 'replace')
    return content


class SmtpdHandler:
    ANSWER_TIMEOUT = 365

    async def handle_PROXY(self, server, session, envelope, proxy_data):
        logger.info(proxy_data)
        return True

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        _, domain = address.split('@')
        if domain != settings.SMTPD_CONFIG['domain']:
            return '550 not relaying to that domain'
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        mail_from = envelope.mail_from
        rcpt_tos = envelope.rcpt_tos
        if len(envelope.rcpt_tos) > 1:
            return '554 Too many recipients'

        msg = email.message_from_bytes(envelope.content)
        plain = html = None
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type.startswith('multipart/'):
                continue
            elif content_type == 'text/plain':
                logger.debug('message: message-part: text/plain')
                plain = _get_content(part)
            elif content_type == 'text/html':
                logger.debug('message: message-part: text/html')
                html = html2text(_get_content(part))
            else:
                logger.info('message: message-part: ' + content_type + ' ignored')

        if not plain and not html:
            return '554 Invalid message format, no content'

        text = plain or html
        recipient = envelope.rcpt_tos[0]
        msg_uuid, _ = recipient.split('@')

        m = re.match(r'ecs-([0-9A-Fa-f]{32})$', msg_uuid)
        if m:
            try:
                orig_msg = await Message.objects.select_related('thread', 'receiver', 'sender').aget(
                    uuid=m.group(1),
                    timestamp__gt=timezone.now() - timedelta(days=self.ANSWER_TIMEOUT)
                )
            except Message.DoesNotExist:
                return '553 Invalid recipient <{}>'.format(recipient)
        else:
            return '553 Invalid recipient <{}>'.format(recipient)

        thread = orig_msg.thread

        creator = msg.get('Auto-Submitted', None)
        # XXX email header are case insentitiv matched,
        # 'auto-submitted' will be matched too it there is no 'Auto-Submitted'
        if creator in (None, '', 'no'):
            creator = 'human'
        elif creator[11] == 'auto-notify':
            creator = 'auto-notify'
        elif creator in ('auto-generated', 'auto-replied'):
            pass
        else:
            creator = 'auto-custom'

        await thread.messages.filter(receiver=orig_msg.receiver).aupdate(unread=False)

        # TODO rawmsg can include multiple content-charsets and should be a binaryfield
        # as a workaround we convert to base64
        thread_msg = await sync_to_async(thread.add_message)(
            orig_msg.receiver, text,
            rawmsg=base64.b64encode(envelope.content),
            incoming_msgid=msg['Message-ID'],
            in_reply_to=orig_msg,
            creator=creator
        )

        logger.info(
            'Accepted email (creator= {8})from {0} via {1} to {2} id {3} in-reply-to {4} thread {5} orig_msg {6} message {7}'.format(
                envelope.mail_from, orig_msg.receiver.email, orig_msg.sender.email,
                msg['Message-ID'], orig_msg.outgoing_msgid, thread.pk,
                orig_msg.pk, thread_msg.pk, creator))

        return '250 Ok'
