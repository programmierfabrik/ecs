import zipfile, os, uuid, datetime
from StringIO import StringIO

from django.utils import simplejson
from django.db import models
from django.core.files.base import File, ContentFile

from ecs.core.models import SubmissionForm, Submission, EthicsCommission, Investigator, InvestigatorEmployee, Measure, \
    ForeignParticipatingCenter, Document, DocumentType, NonTestedUsedDrug

DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
DATE_FORMAT = '%Y-%m-%d'
DATA_JSON_NAME = 'data.json'

class ModelSerializer(object):
    exclude = ('id',)
    groups = ()
    follow = ()
    fields = ()

    def __init__(self, model, groups=None, exclude=None, follow=None, fields=None):
        self.model = model
        if groups:
            self.groups = groups
        if exclude:
            self.exclude = exclude
        if follow:
            self.follow = follow
        if fields:
            self.fields = fields
            
    def get_field_names(self):
        names = set(f.name for f in self.model._meta.fields if f.name not in self.exclude)
        if self.fields:
            names = names.intersection(self.fields)
        return names.union(self.follow)
        
    def split_prefix(self, name):
        prefix, key = None, name
        for group in self.groups:
            if name.startswith(group):
                prefix, key = group, name[len(group)+1:]
                break
        return prefix, key
        
    def dump_field(self, fieldname, val, zf):
        if val is None or isinstance(val, (bool, basestring, int, long, datetime.datetime, datetime.date)):
            return val
        if hasattr(val, 'all') and hasattr(val, 'count'):
            return [dump_model_instance(x, zf) for x in val.all()]
        
        field = self.model._meta.get_field(fieldname)

        if isinstance(field, models.ForeignKey):
            return dump_model_instance(val, zf)
        elif isinstance(field, models.FileField):
            name, ext = os.path.splitext(val.name)
            zip_name = 'attachments/%s%s' % (uuid.uuid4(), ext)
            zf.write(val.path, zip_name)
            return zip_name
        else:
            raise TypeError("cannot serialize objecs of type %s" % type(val))
        
        return val

    def dump(self, obj, zf):
        d = {}
        for name in self.get_field_names():
            prefix, key = self.split_prefix(name)
            data = self.dump_field(name, getattr(obj, name), zf)
            if prefix:
                d.setdefault(prefix, {})
                d[prefix][key] = data
            else:
                d[name] = data
        return d
        
    def load_many(self, model, val, zf, commit=True):
        return [load_model_instance(model, data, zf, commit=commit) for data in val]
        
    def load_field(self, fieldname, val, zf):
        if val is None:
            return val, False
        try:
            field = self.model._meta.get_field(fieldname)
        except models.fields.FieldDoesNotExist:
            field = None
        deferr = False
        if field:
            if isinstance(field, models.DateTimeField):
                val = datetime.datetime.strptime(val, DATETIME_FORMAT)
            elif isinstance(field, models.DateField):
                val = datetime.date.strptime(val, DATE_FORMAT)
            elif isinstance(field, models.ManyToManyField):
                val = self.load_many(field.related.parent_model, val, zf)
                deferr = True
            elif isinstance(field, models.FileField):
                f = ContentFile(zf.read(val))
                f.name = val # we hack in a name, to force django to automatically save the ContentFile on Model.save()
                val = f
            elif isinstance(field, models.ForeignKey):
                val = load_model_instance(field.rel.to, val, zf)
        elif isinstance(val, list):
            rel_model = getattr(self.model, fieldname).related.model
            val = self.load_many(rel_model, val, zf, commit=False)
            deferr = True
        return val, deferr
        
    def load(self, data, zf, commit=True):
        deferred = []
        fields = {}
        obj = self.model()
        for name in self.get_field_names():
            prefix, key = self.split_prefix(name)
            if prefix:
                if prefix in data:
                    val = data[prefix][key]
                else:
                    continue
            elif key in data:
                val = data[key]
            else:
                continue
            val, deferr = self.load_field(name, val, zf)
            if deferr:
                deferred.append((name, val, deferr))
            else:
                fields[name] = val
        obj = self.model(**fields)
        obj.clean()
        old_save = obj.save
        def _save(*args, **kwargs):
            old_save(*args, **kwargs)
            for name, val, action in deferred:
                manager = getattr(obj, name)
                for item in val:
                    manager.add(item)
        obj.save = _save
        if commit:
            obj.save()
        return obj

class DocumentTypeSerializer(object):
    def load(self, data, zf, commit=True):
        try:
            return DocumentType.objects.get(name=data)
        except DocumentType.DoesNotExist:
            raise ValueError("no such doctype: %s" % data)
        
    def dump(self, obj, zf):
        return obj.name

class EthicsCommissionSerializer(object):
    def load(self, data, zf, commit=False):
        try:
            return EthicsCommission.objects.get(pk=data)
        except EthicsCommission.DoesNotExist:
            raise ValueError("no such ethicscommission: %s" % data)
            
    def dump(self, obj, zf):
        return obj.pk
        
class SubmissionSerializer(ModelSerializer):
    def __init__(self, **kwargs):
        super(SubmissionSerializer, self).__init__(Submission, **kwargs)
        
    def load(self, data, zf, commit=False):
        try:
            return Submission.objects.get(ec_number=data.get('ec_number'))
        except Submission.DoesNotExist:
            return super(SubmissionSerializer, self).load(data, zf, commit=commit)

_serializers = {
    SubmissionForm: ModelSerializer(SubmissionForm,
        groups = ('study_plan', 'insurance', 'sponsor', 'invoice', 'german', 'submitter', 'project_type', 'medtech', 'substance', 'subject'),
        follow = ('foreignparticipatingcenter_set', 'investigators', 'measures', 'documents', 'nontesteduseddrug_set')
    ),
    Submission: SubmissionSerializer(),
    Investigator: ModelSerializer(Investigator, exclude=('id', 'submission_form'), follow=('employees',)),
    InvestigatorEmployee: ModelSerializer(InvestigatorEmployee, exclude=('id', 'investigator')),
    Measure: ModelSerializer(Measure, exclude=('id', 'submission_form')),
    ForeignParticipatingCenter: ModelSerializer(ForeignParticipatingCenter, exclude=('id', 'submission_form')),
    NonTestedUsedDrug: ModelSerializer(NonTestedUsedDrug, exclude=('id', 'submission_form')),
    Document: ModelSerializer(Document, fields=('doctype', 'file', 'date', 'version', 'mimetype')),
    DocumentType: DocumentTypeSerializer(),
    EthicsCommission: EthicsCommissionSerializer(),
}

def load_model_instance(model, data, zf, commit=True):
    if model not in _serializers:
        raise TypeError("cannot load objects of type %s" % model)
    return _serializers[model].load(data, zf, commit=commit)

def dump_model_instance(obj, zf):
    if obj.__class__ not in _serializers:
        raise TypeError("cannot serialize objecs of type %s" % obj.__class__)
    return _serializers[obj.__class__].dump(obj, zf)
    
class _JsonEncoder(simplejson.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime(DATETIME_FORMAT)
        elif isinstance(obj, datetime.date):
            return obj.strftime(DATE_FORMAT)
        return super(Encoder, self).default(obj)

class Serializer(object):
    version = '0.1'

    def read(self, file_like):
        zf = zipfile.ZipFile(file_like, 'r')
        data = simplejson.loads(zf.read(DATA_JSON_NAME))
        submission_form = _serializers[SubmissionForm].load(data['data'], zf)
        return submission_form
    
    def write(self, submission_form, file_like):
        zf = zipfile.ZipFile(file_like, 'w', zipfile.ZIP_DEFLATED)

        data = {
            'version': self.version,
            'timestamp': datetime.datetime.now(),
            'type': 'SubmissionForm',
            'data': dump_model_instance(submission_form, zf),
        }
        json = simplejson.dumps(data, cls=_JsonEncoder, indent=2)
        zf.writestr(DATA_JSON_NAME, json)
        
            