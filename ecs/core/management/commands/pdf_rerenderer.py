from django.core.management.base import BaseCommand

from ecs.core.tasks import render_submission_form


class Command(BaseCommand):
    help = "Command description."

    def add_arguments(self, parser):
        parser.add_argument(
            '--submissionform',
            type=int,
            help='ID of the submission form',
        )
        # parser.add_argument(
        #     '--notification',
        #     type=int,
        #     help='ID of the notification',
        # )

    def handle(self, *args, **options):
        if options['submissionform'] is not None:
            render_submission_form(options['submissionform'])
        # elif options['notification'] is not None:
        #     try:
        #         notification = Notification.objects.get(pk=options['notification'])
        #         if notification.pdf_document is None:
        #             notification.render_pdf_document()
        #         else:
        #             pdfdata = notification.render_pdf()
        #             # Delete old pdf
        #             del getVault()[notification.pdf_document.uuid.hex]
        #             # Create new pdf in place
        #             with tempfile.TemporaryFile() as f:
        #                 f.write(pdfdata)
        #                 f.flush()
        #                 f.seek(0)
        #                 notification.pdf_document.store(f)
        #     except Notification.DoesNotExist:
        #         print("notification(id=%d) doesn't exist" % options['notification'])
