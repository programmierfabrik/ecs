import os

from django.conf import settings
from django.utils.translation import gettext_noop as _

from ecs import bootstrap
from ecs.documents.models import DocumentType
from ecs.utils import Args


@bootstrap.register()
def document_types():
    names = (
        Args(_("Cover Letter (CL)"), "coveringletter"),
        Args(_("SIS-ICF"), "patientinformation"),
        Args(_("Insurance Documents"), "insurancecertificate"),
        Args(_("Protocol"), "protocol"),
        Args(_("Investigator's Brochure (IB)"), "investigatorsbrochure", is_downloadable=False),
        Args(_("Amendment"), "amendment", is_hidden=True),
        Args(_("Curriculum Vitae (CV)"), "cv"),
        Args(_("Conflict of Interest (CoI)"), "conflictofinterest"),
        Args(_("Case Report Form (CRF)"), "crf"),
        Args(_("EudraCT-Form"), "eudract"),
        Args(_("Side effects report"), "adversereaction"),
        Args(_("Statement on the report"), "reviewstatement"),
        Args(_("Questionnaire"), "questionnaire"),
        Args(_("Signature page"), "signed_page"),
        Args(_("Instructions for use"), "manual"),
        Args(_("Declaration of Conformity"), "conformity_declaration"),
        Args(_("Others / miscellaneous"), "other"),
        Args(_("GCP-Certificate"), "gcp_certificate"),
        Args(_("Statistics"), "statistics"),
        Args(_("recruitment materials"), "recruitment_material"),

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
        Args(_("Meeting Document"), "meeting_documents", is_hidden=True),
        Args(_("Supporting Document"), "supporting_documents", is_hidden=True),
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
