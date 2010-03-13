import uuid, datetime
from django.db import models
from django.http import QueryDict
from django.utils.functional import wraps

from django_extensions.db.fields.json import JSONField

from ecs.docstash.exceptions import ConcurrentModification, UnknownVersion

def _transaction_required(method):
    @wraps(method)
    def decorated(self, *args, **kwargs):
        if not hasattr(self, '_transaction'):
            raise TypeError('DocStash.%s() must be called from within a DocStash transaction' % method.__name__)
        return method(self, *args, **kwargs)
    return decorated

class DocStash(models.Model):
    key = models.CharField(max_length=41, primary_key=True)
    group = models.CharField(max_length=120, db_index=True, null=True)
    current_version = models.IntegerField(default=-1)
    deleted = models.BooleanField(default=False)

    def save(self, force_insert=None, force_update=None):
        if not self.key:
            self.key = uuid.uuid4().hex
        super(DocStash, self).save(force_insert=force_insert, force_update=force_update)
        
    @property
    def current_value(self):
        if not hasattr(self, '_value_cache'):
            if self.current_version == -1:
                self._value_cache = {}
            else:
                self._value_cache = self.data.get(version=self.current_version).value
        return self._value_cache
        
    def start_transaction(self, version, name=None, user=None):
        if hasattr(self, '_transaction'):
            raise TypeError('transaction already started')
        if version == -1:
            value = {}
        else:
            try:
                value = self.data.get(version=version).value
            except DocStashData.DoesNotExist:
                raise UnknownVersion("key=%s, version=%s" % (self.key, version))
        self._transaction = DocStashData(stash=self, version=version+1, value=value, name=name or "")
    
    @_transaction_required
    def commit_transaction(self):
        if self._transaction.is_dirty():
            # the following update query should be atomic (with Transaction Isolation Level "Read committed" or better)
            # it serves as a guard against race conditions:
            if not DocStash.objects.filter(key=self.key, current_version=self.current_version).update(current_version=models.F('current_version') + 1):
                raise ConcurrentModification()
            else:
                self.current_version += 1
                self._transaction.save()
                if hasattr(self, '_value_cache'):
                    del self._value_cache
        del self._transaction
    
    @_transaction_required
    def rollback_transaction(self):
        del self._transaction
    
    @_transaction_required
    def _set_value(self, value):
        self._transaction._dirty = True
        self._transaction.value = value
    
    @_transaction_required
    def _get_value(self):
        return self._transaction.value
        
    value = property(_get_value, _set_value)


def _create_docstash_transaction_data_proxy(method):
    @_transaction_required
    def proxy(self, *args, **kwargs):
        return getattr(self._transaction, method)(*args, **kwargs)
    proxy.__name__ = method
    return proxy

for method in ('post', 'get', '__getitem__', '__setitem__', 'update', 'get_query_dict'):
    setattr(DocStash, method, _create_docstash_transaction_data_proxy(method))


class DocStashData(models.Model):
    version = models.IntegerField()
    stash = models.ForeignKey(DocStash, related_name='data')
    value = JSONField()
    modtime = models.DateTimeField(default=datetime.datetime.now)
    name = models.CharField(max_length=120, blank=True)
    
    class Meta:
        unique_together = ('version', 'stash')
        
    def __str__(self):
        return "stash_key=%s, version=%s" % (self.stash.key, self.version)
        
    def is_dirty(self):
        return getattr(self, '_dirty', False)

    def post(self, query_dict, exclude=None):
        self._dirty = True
        if not exclude:
            exclude = lambda name: False
        self.value = dict((name, value_list) for name, value_list in query_dict.iterlists() if not exclude(name))

    def update(self, d):
        self._dirty = True
        self.value.update(d)

    def __setitem__(self, name, value):
        self._dirty = True
        self.value[name] = value

    def get(self, name, default=None):
        return self.value.get(name, default)

    def __getitem__(self, name):
        return self.value[name]

    def get_query_dict(self):
        query_dict = QueryDict("", mutable=True)
        for name, value in self.value.iteritems():
            query_dict.setlist(name, value)
        return query_dict
