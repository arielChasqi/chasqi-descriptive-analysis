from django.test import TestCase
from datetime import datetime
import pytz
# Create your tests here.
from evaluation.services.kpi_calculator import get_kpi_evaluation
from .services.custom_performance import get_evaluation_range_by_percentage


class CustomPerformanceTestCase(TestCase):
    def test_get_evaluation_range_by_percentage(self):
        # Supón que el tenant_id es 'test_tenant' y un porcentaje de 85
        performance = get_evaluation_range_by_percentage(85, 'chasqi')

        # Verifica que el desempeño tiene un valor esperado
        self.assertEqual(performance['title'], "Muy Bueno")  # Ejemplo de título esperado
        self.assertEqual(performance['color'], "#D2E986")  # Ejemplo de color esperado
        self.assertGreater(performance['minValue'], 79)  # Verifica que el minValue sea mayor que 80

class KpiCalculatorTestCase(TestCase):
    def test_get_evaluation(self):
        self.tenant_id = "chasqi"
        self.task_id = "67b61f27441df99098200f5f"
        self.colaborador_id = "67b61998441df990982006fa"

        # Establecer fechas de inicio y fin con los valores específicos en UTC
        tz = pytz.timezone('UTC')

        self.start_date = tz.localize(datetime(2025, 1, 1, 5, 0, 0))  # 2025-01-01T05:00:00.000Z
        self.end_date = tz.localize(datetime(2025, 2, 1, 4, 59, 59, 999000))  # 2025-02-01T04:59:59.999Z

        self.kpi_data = {
            "Filtro_de_fecha" : "hs_activity_date",
            "Campo_a_evaluar": "Record_ID",
            "Formula": "count",
            "Objetivo": 25,
            "Unidad_de_tiempo": 1,
            "Dias_no_laborales": [1, 3, 5, 6],
            "Filters": [{}]
        }

        result = get_kpi_evaluation(
            task_id=self.task_id,  # ID del task asociado al KPI
            kpi_data=self.kpi_data,
            tenant_id=self.tenant_id,
            colaborador_id=self.colaborador_id,
            start_date=self.start_date,
            end_date=self.end_date
        )

        # Verifica que el resultado sea un diccionario y que contenga los campos esperados
        self.assertIsInstance(result, dict)
        self.assertEqual(result["kpiPercentage"], 29.57)
        self.assertEqual(result["totalCount"], 170)
        self.assertEqual(result["daysConsidered"], 23)
        self.assertEqual(result["targetSales"], 575)
        self.assertEqual(result["nonConsideredDaysCount"], 8)
        
