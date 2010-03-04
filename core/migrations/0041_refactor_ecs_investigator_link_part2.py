# -*- coding: utf-8 -*-

from south.db import db
from django.db import models
from core.models import *

class Migration:
    
    def forwards(self, orm):
        
        # Deleting model 'involvedcommissionsforsubmission'
        db.delete_table('core_involvedcommissionsforsubmission')
        
    
    
    def backwards(self, orm):
        # Adding model 'involvedcommissionsforsubmission'
        db.create_table('core_involvedcommissionsforsubmission', (
            ('submission', orm['core.submissionform:submission']),
            ('commission', orm['core.submissionform:commission']),
            ('examiner_name', orm['core.submissionform:examiner_name']),
            ('main', orm['core.submissionform:main']),
            ('id', orm['core.submissionform:id']),
        ))
        db.send_create_signal('core', ['involvedcommissionsforsubmission'])
        
    
    
    models = {
        'core.amendment': {
            'date': ('django.db.models.fields.DateField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'number': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'order': ('django.db.models.fields.IntegerField', [], {}),
            'submissionform': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']"})
        },
        'core.basenotificationform': {
            'comments': ('django.db.models.fields.TextField', [], {'default': "''", 'blank': 'True'}),
            'date_of_vote': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'ek_number': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '40', 'blank': 'True'}),
            'ethics_commissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.EthicsCommission']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'investigator': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Investigator']", 'null': 'True', 'blank': 'True'}),
            'notification': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'forms'", 'null': 'True', 'to': "orm['core.Notification']"}),
            'signed_on': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'submission_forms': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.SubmissionForm']"}),
            'type': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'notification_forms'", 'null': 'True', 'to': "orm['core.NotificationType']"})
        },
        'core.checklist': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'core.diagnosticsapplied': {
            'count': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'period': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']"}),
            'total': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '30'})
        },
        'core.document': {
            'absent': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'date': ('django.db.models.fields.DateTimeField', [], {}),
            'doctype': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.DocumentType']", 'null': 'True', 'blank': 'True'}),
            'file': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mimetype': ('django.db.models.fields.CharField', [], {'default': "'application/pdf'", 'max_length': '100'}),
            'uuid_document': ('django.db.models.fields.SlugField', [], {'max_length': '32', 'db_index': 'True'}),
            'uuid_document_revision': ('django.db.models.fields.SlugField', [], {'max_length': '32', 'db_index': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '250'})
        },
        'core.documenttype': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '100'})
        },
        'core.ethicscommission': {
            'address_1': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'address_2': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'chairperson': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'contactname': ('django.db.models.fields.CharField', [], {'max_length': '120', 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'}),
            'fax': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200', 'null': 'True'}),
            'zip_code': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        'core.extendednotificationform': {
            'SAE_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'SUSAR_count': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'aborted_on': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'aborted_subjects': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'basenotificationform_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['core.BaseNotificationForm']", 'unique': 'True', 'primary_key': 'True'}),
            'extension_of_vote': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'finished_on': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'}),
            'finished_subjects': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'reason_for_not_started': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'recruited_subjects': ('django.db.models.fields.IntegerField', [], {'null': 'True', 'blank': 'True'}),
            'runs_till': ('django.db.models.fields.DateField', [], {'null': 'True', 'blank': 'True'})
        },
        'core.investigator': {
            'certified': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'commission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.EthicsCommission']", 'null': 'True'}),
            'email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'fax': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'jus_practicandi': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'main_investigator': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'mobile': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'organisation': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'phone': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'sign_date': ('django.db.models.fields.DateField', [], {}),
            'specialist': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'subject_count': ('django.db.models.fields.IntegerField', [], {}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']"})
        },
        'core.investigatoremployee': {
            'firstname': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'organisation': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'sex': ('django.db.models.fields.CharField', [], {'max_length': '1'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Investigator']"}),
            'surname': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '40'})
        },
        'core.involvedcommissionsfornotification': {
            'commission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.EthicsCommission']"}),
            'examiner_name': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '120'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'main': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.BaseNotificationForm']"})
        },
        'core.meeting': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submissions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Submission']"})
        },
        'core.nontesteduseddrugs': {
            'dosage': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'generic_name': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'preparation_form': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']"})
        },
        'core.notification': {
            'answer': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.NotificationAnswer']", 'null': 'True'}),
            'documents': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Document']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Submission']", 'null': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Workflow']", 'null': 'True'})
        },
        'core.notificationanswer': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Workflow']"})
        },
        'core.notificationtype': {
            'form': ('django.db.models.fields.CharField', [], {'default': "'ecs.core.forms.BaseNotificationForm'", 'max_length': '80'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'model': ('django.db.models.fields.CharField', [], {'default': "'ecs.core.models.BaseNotificationForm'", 'max_length': '80'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '40'})
        },
        'core.participatingcenter': {
            'address_1': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'address_2': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'city': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'country': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '60'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']"}),
            'zip_code': ('django.db.models.fields.CharField', [], {'max_length': '10'})
        },
        'core.submission': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submissionreview': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionReview']", 'null': 'True'}),
            'vote': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Vote']", 'null': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Workflow']", 'null': 'True'})
        },
        'core.submissionform': {
            'additional_therapy_info': ('django.db.models.fields.TextField', [], {}),
            'already_voted': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'clinical_phase': ('django.db.models.fields.CharField', [], {'max_length': '10'}),
            'date_of_protocol': ('django.db.models.fields.DateField', [], {}),
            'documents': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Document']"}),
            'eudract_number': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'german_abort_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_additional_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_aftercare_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_benefits_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_concurrent_study_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_consent_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_dataaccess_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_dataprotection_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_ethical_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_financing_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_inclusion_exclusion_crit': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_payment_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_preclinical_results': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_primary_hypothesis': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_project_title': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_protected_subjects_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_recruitment_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_relationship_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_risks_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_sideeffects_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_statistical_info': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'german_summary': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'insurance_address_1': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'insurance_contract_number': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'insurance_name': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'insurance_phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'insurance_validity': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'investigator_certified': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'investigator_email': ('django.db.models.fields.EmailField', [], {'max_length': '75'}),
            'investigator_fax': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'investigator_jus_practicandi': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'investigator_mobile': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'investigator_name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'investigator_organisation': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'investigator_phone': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'investigator_specialist': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'invoice_address1': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'invoice_address2': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'invoice_city': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'invoice_contactname': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'invoice_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'}),
            'invoice_fax': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'invoice_name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'invoice_phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'invoice_uid': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'invoice_uid_verified_level1': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'invoice_uid_verified_level2': ('django.db.models.fields.DateTimeField', [], {'null': 'True'}),
            'invoice_zip_code': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True'}),
            'isrctn_number': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'medtech_ce_symbol': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'medtech_certified_for_exact_indications': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'medtech_certified_for_other_indications': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'medtech_checked_product': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'medtech_departure_from_regulations': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'medtech_manual_included': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'medtech_manufacturer': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'medtech_product_name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'medtech_reference_substance': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'medtech_technical_safety_regulations': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'pharma_checked_substance': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'pharma_reference_substance': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'project_title': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'project_type_2_1_1': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_2': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_2_1': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_2_2': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_3': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_4': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_4_1': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_4_2': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_4_3': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_5': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_6': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_7': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_8': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'project_type_2_1_9': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'protocol_number': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'specialism': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'sponsor_address1': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'sponsor_address2': ('django.db.models.fields.CharField', [], {'max_length': '60', 'null': 'True'}),
            'sponsor_city': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'sponsor_contactname': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'sponsor_email': ('django.db.models.fields.EmailField', [], {'max_length': '75', 'null': 'True'}),
            'sponsor_fax': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'sponsor_name': ('django.db.models.fields.CharField', [], {'max_length': '80', 'null': 'True'}),
            'sponsor_phone': ('django.db.models.fields.CharField', [], {'max_length': '30', 'null': 'True'}),
            'sponsor_zip_code': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True'}),
            'study_plan_8_1_1': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_10': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_11': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_12': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_13': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_14': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_15': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_16': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_17': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_18': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_19': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_2': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_20': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_21': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_22': ('django.db.models.fields.TextField', [], {'default': "''", 'null': 'True'}),
            'study_plan_8_1_3': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_4': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_5': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_6': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_7': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_8': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_1_9': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_3_1': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_8_3_2': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'study_plan_abort_crit': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_alpha': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_biometric_planning': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'study_plan_datamanagement': ('django.db.models.fields.TextField', [], {}),
            'study_plan_dataprotection_anonalgoritm': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'study_plan_dataprotection_dvr': ('django.db.models.fields.CharField', [], {'max_length': '12'}),
            'study_plan_dataprotection_reason': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'study_plan_dataquality_checking': ('django.db.models.fields.TextField', [], {}),
            'study_plan_dropout_ratio': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_multiple_test_correction_algorithm': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_planned_statalgorithm': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_power': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_statalgorithm': ('django.db.models.fields.CharField', [], {'max_length': '40'}),
            'study_plan_statistics_implementation': ('django.db.models.fields.CharField', [], {'max_length': '120'}),
            'subject_childbearing': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'subject_count': ('django.db.models.fields.IntegerField', [], {}),
            'subject_duration': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'subject_duration_active': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'subject_duration_controls': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'subject_females': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'subject_males': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'subject_maxage': ('django.db.models.fields.IntegerField', [], {}),
            'subject_minage': ('django.db.models.fields.IntegerField', [], {}),
            'subject_noncompetents': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'subject_planned_total_duration': ('django.db.models.fields.CharField', [], {'max_length': '20'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'forms'", 'to': "orm['core.Submission']"}),
            'submitter_is_authorized_by_sponsor': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'submitter_is_coordinator': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'submitter_is_main_investigator': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'submitter_is_sponsor': ('django.db.models.fields.BooleanField', [], {'default': 'False', 'blank': 'True'}),
            'submitter_jobtitle': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'submitter_name': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'submitter_organisation': ('django.db.models.fields.CharField', [], {'max_length': '80'}),
            'submitter_sign_date': ('django.db.models.fields.DateField', [], {}),
            'substance_p_c_t_application_type': ('django.db.models.fields.CharField', [], {'max_length': '40', 'null': 'True'}),
            'substance_p_c_t_countries': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True'}),
            'substance_p_c_t_final_report': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'substance_p_c_t_gcp_rules': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'substance_p_c_t_period': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'substance_p_c_t_phase': ('django.db.models.fields.CharField', [], {'max_length': '10', 'null': 'True'}),
            'substance_preexisting_clinical_tries': ('django.db.models.fields.NullBooleanField', [], {'null': 'True'}),
            'substance_registered_in_countries': ('django.db.models.fields.CharField', [], {'max_length': '300', 'null': 'True'})
        },
        'core.submissionreview': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Workflow']"})
        },
        'core.therapiesapplied': {
            'count': ('django.db.models.fields.IntegerField', [], {'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'period': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'submission': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']"}),
            'total': ('django.db.models.fields.CharField', [], {'max_length': '30'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '30'})
        },
        'core.vote': {
            'checklists': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['core.Checklist']"}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'submissionform': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.SubmissionForm']", 'null': 'True'}),
            'votereview': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.VoteReview']"}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Workflow']"})
        },
        'core.votereview': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'workflow': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['core.Workflow']"})
        },
        'core.workflow': {
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }
    
    complete_apps = ['core']
