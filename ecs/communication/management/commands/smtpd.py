import logging
import os
import ssl
from os.path import isfile

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import SMTP as Server
from django.core.management.base import BaseCommand

from ecs import settings
from ecs.communication.smtpd import SmtpdHandler

log2level = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO,
             'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
             'CRITICAL': logging.CRITICAL}

logger = logging.getLogger(__name__)


class SmtpController(Controller):
    def factory(self):
        if isfile('/opt/certs/fullchain.pem') or True:
            logger.info("Found fullchain.pem and key.pem...")
            tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            tls_context.load_cert_chain('/opt/certs/fullchain.pem', '/opt/certs/key.pem')
            logger.info("Loaded fullchain.pem and key.pem...")
        else:
            tls_context = None

        time_out = 3 if os.getenv('PROXY', '').lower() == 'true' else None
        require_starttls = True if tls_context is not None else None

        return Server(
            self.handler, proxy_protocol_timeout=time_out, require_starttls=require_starttls, tls_context=tls_context
        )


class Command(BaseCommand):
    help = 'Run receiving SMTP server.'

    def add_arguments(self, parser):
        parser.add_argument('-l', '--loglevel', action='store',
                            choices=['debug', 'info', 'warning', 'error', 'critical'],
                            dest='loglevel', default='info', help='set loglevel'
                            )

    def handle(self, **options):
        logging.basicConfig(
            level=log2level[options['loglevel'].upper()],
            format='%(levelname)s %(message)s',
        )

        hostname, port = settings.SMTPD_CONFIG['listen_addr']
        controller = SmtpController(SmtpdHandler(), hostname=hostname, port=port)
        controller.start()
        # Consider a solution like this instead of accessing a private thread and join it:
        # https://github.com/aio-libs/aiosmtpd/blob/d6976db28721c4afa06755c3c10be358a2553b7d/examples/basic/server.py
        controller._thread.join()
        controller.stop()
