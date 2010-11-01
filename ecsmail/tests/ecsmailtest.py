# -*- coding: utf-8 -*-

import os
import re
from nose.tools import assert_raises, ok_, eq_
from django.conf import settings
from lamson.server import SMTPError

from ecs.ecsmail.testcases import MailTestCase

class ecsmailIncomingTest(MailTestCase):
    def test_relay(self):
        ''' test relaying ''' 
        assert_raises(SMTPError, self.receive,
            "some subject", "some body",
            "".join(("ecs-123@", settings.ECSMAIL ['authoritative_domain'])),
            "tooutside@someplace.org")

    def test_to_us_unknown(self):
        ''' mail to us, but unknown receipient address at our site '''
        assert_raises(SMTPError, self.receive,
            "some subject", "some body",
            "nobody@notexisting.loc",
            "".join(("ecs-123@", settings.ECSMAIL ['authoritative_domain'])),
             )

class ecsmailOutgoingTest(MailTestCase):
    def test_hello_world(self):
        self.deliver("some subject", "some body, first message")
        eq_(self.queue_count(), 1)
        ok_(self.is_delivered("first message"))
    
    def test_text_and_html(self):
        self.deliver("another subject", "second message", message_html= "<b> this is bold</b>")
        x = self.is_delivered("second message")
        ok_(x)
        msg = self.convert_raw2message(x)
        mimetype, html_data = self.get_mimeparts(msg, "text", "html") [0]
        ok_(re.search("this is bold", html_data))
    
    def test_attachment(self):
        attachment_name = os.path.join(settings.PROJECT_DIR, "core", "tests", "data", "menschenrechtserklaerung.pdf")
        attachment_data = open(attachment_name, "rb").read()
        
        self.deliver("another subject, plus attachment", "this comes with attachment", attachments=[attachment_name])
        x = self.is_delivered("with attachment")
        ok_(x)
   
        msg = self.convert_raw2message(x)
        mimetype, pdf_data = self.get_mimeparts(msg, "application", "pdf") [0]
        eq_(attachment_data, pdf_data)
        
    def test_text_and_html_and_attachment(self):
        attachment_name = os.path.join(settings.PROJECT_DIR, "core", "tests", "data", "menschenrechtserklaerung.pdf")
        attachment_data = open(attachment_name, "rb").read()
        
        self.deliver("another subject, plus attachment", "another attachment", 
            message_html= "<b>bold attachment</b>", attachments=[attachment_name])
        x = self.is_delivered("plus attachment")
        ok_(x)
        
        msg = self.convert_raw2message(x)
        mimetype, html_data = self.get_mimeparts(msg, "text", "html") [0]
        mimetype, pdf_data = self.get_mimeparts(msg, "application", "pdf") [0]
        
        ok_(re.search("<b>bold attachment</b>", html_data))
        eq_(attachment_data, pdf_data)
        