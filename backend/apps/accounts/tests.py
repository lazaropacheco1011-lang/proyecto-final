from pathlib import Path

from django.test import TestCase
from django.urls import reverse


class AdminRedirectTests(TestCase):
    def test_administrador_redirects_to_admin(self):
        response = self.client.get(reverse('administrador_redirect'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/admin/')

    def test_home_serves_frontend_index(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RefriMaster')
