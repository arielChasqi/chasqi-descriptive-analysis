from django.test import TestCase

# Create your tests here.
from .services.custom_performance import get_evaluation_range_by_percentage

class CustomPerformanceTestCase(TestCase):
    def test_get_evaluation_range_by_percentage(self):
        # Supón que el tenant_id es 'test_tenant' y un porcentaje de 85
        performance = get_evaluation_range_by_percentage(85, 'chasqi')

        # Verifica que el desempeño tiene un valor esperado
        self.assertEqual(performance['title'], "Muy Bueno")  # Ejemplo de título esperado
        self.assertEqual(performance['color'], "#D2E986")  # Ejemplo de color esperado
        self.assertGreater(performance['minValue'], 79)  # Verifica que el minValue sea mayor que 80
