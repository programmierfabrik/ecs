from django.core.urlresolvers import reverse
from ecs.utils.testcases import LoginTestCase, EcsTestCase

class ImportTest(EcsTestCase):
    ''' Check if base and core urls,view,models are importable '''
    
    def test_import(self):
        "Tests if the urls module and core.urls, core.views, core.models are importable"
        
        
class CoreUrlsTest(LoginTestCase):
    '''High level tests for accessibility of core views of the system.'''
    
    def test_index(self):
        '''Tests if the Dashboard/main-site of the system is accessible.'''
        
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        
    def test_submission_forms(self):
        '''Tests if the all-submissions view of the system is accessible.'''
        
        response = self.client.get(reverse('core.submission.all_submissions'))
        self.assertEqual(response.status_code, 200)

