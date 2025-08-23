from django.test import TestCase
from .registry import get
from .magfa import MAGFA_TYPE, MagfaProvider

class RegistryTest(TestCase):
    def test_registry(self):
        self.assertIs(get(MAGFA_TYPE), MagfaProvider)
