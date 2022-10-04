import logging

from aiosmtpd.controller import Controller
from django.core.management.base import BaseCommand

from ecs import settings
from ecs.communication.smtpd import SmtpdHandler

log2level = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO,
             'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
             'CRITICAL': logging.CRITICAL}


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
        controller = Controller(SmtpdHandler(), hostname=hostname, port=port)
        controller.start()
        input('SMTP server running. Press Return to stop server and exit.')
        controller.stop()
