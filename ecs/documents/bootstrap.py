import os

from django.conf import settings
from django.utils.translation import gettext_noop as _

from ecs import bootstrap
from ecs.documents.models import DocumentType
from ecs.utils import Args


@bootstrap.register()
def document_types():
    names = (
        Args(_("Covering Letter"), "coveringletter"),
        Args(_("patient information"), "patientinformation"),
        Args(_("insurancecertificate"), "insurancecertificate"),
        Args(_("study protocol"), "protocol"),
        Args(_("Investigator's Brochure"), "investigatorsbrochure", is_downloadable=False),
        Args(_("Amendment"), "amendment", is_hidden=True),
        Args(_("Curriculum Vitae (CV)"), "cv"),
        Args(_("Conflict of Interest"), "conflictofinterest"),
        Args(_("Case Report Form (CRF)"), "crf"),
        Args(_("EudraCT Form"), "eudract"),
        Args(_("adverse reaction report"), "adversereaction"),
        Args(_("Statement on a review"), "reviewstatement"),
        Args(_("Questionnaire"), "questionnaire"),
        Args(_("Signed Page"), "signed_page"),
        Args(_("Manual"), "manual"),
        Args(_("Declaration of conformity"), "conformity_declaration"),
        Args(_("other"), "other"),
        Args(_("gcp-certificate"), "gcp_certificate"),
        Args(_("statistic / statistic documents"), "statistics"),
        Args(_("recruitment material"), "recruitment_material"),

        # internal document types; not user visible
        Args(_("Submission Form"), "submissionform", is_hidden=True),
        Args(_("Checklist"), "checklist", is_hidden=True),
        Args(_("vote"), "votes", is_hidden=True),
        Args(_("Notification"), "notification", is_hidden=True),
        Args(_("Notification Answer"), "notification_answer", is_hidden=True),
        Args(_("Invoice"), "invoice", is_hidden=True),
        Args(_("Checklist Payment"), "checklist_payment", is_hidden=True),
        Args(_("Meeting Protocol"), "meeting_protocol", is_hidden=True),
        Args(_("Meeting ZIP"), "meeting_zip", is_hidden=True),
    )

    for args in names:
        name, identifier = args
        DocumentType.objects.update_or_create(identifier=identifier, defaults={
            'name': name,
            'is_hidden': args.get('is_hidden', False),
            'is_downloadable': args.get('is_downloadable', True),
        })


@bootstrap.register()
def create_local_storage_vault():
    os.makedirs(settings.STORAGE_VAULT, exist_ok=True)
