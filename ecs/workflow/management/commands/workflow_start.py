from django.core.management.base import BaseCommand
from ecs.core.models import Submission
from ecs.workflow.models import Graph

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--submission', '-s', dest='submission_pk', type=int, help="A submission id")

    def handle(self, submission_pk=None, **options):
        s = Submission.objects.get(id=submission_pk)
        print(s.ec_number, s.project_title)
        wf = Graph.objects.get().create_workflow(data=s)
        wf.start()
