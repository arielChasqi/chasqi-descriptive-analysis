from django.test import TestCase
from datetime import datetime
import pytz
import json
import time
# Create your tests here.
from evaluation.services.kpi_calculator import get_kpi_evaluation
from evaluation.services.evaluation_cache import get_cached_or_fresh_evaluation
from evaluation.utils.redis_client import redis_client
from .services.custom_performance import get_evaluation_range_by_percentage
from .services.evaluations_analysis import calculate_evaluation_for_employees

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
        
class EvaluationCacheIntegrationTest(TestCase):
    def setUp(self):
        self.tenant_id = "chasqi"
        self.evaluation_id = "67b772bfaf33bc64b4d5394c"

        #Limpia la cache antes de cada prueba
        self.redis_key = f"tenant:{self.tenant_id}:evaluation:{self.evaluation_id}"
        redis_client.delete(self.redis_key)
    
    def test_get_evaluation_and_cache_it(self):
        #Primera vez: trae de MongoDB y guarda en Redis
        evaluation = get_cached_or_fresh_evaluation(self.tenant_id, self.evaluation_id)
        self.assertIsInstance(evaluation, dict)
        self.assertIn("Secciones", evaluation)

        #Asegura que las secciones tienen KPIs enriquecidos
        for seccion in evaluation["Secciones"]:
            for kpi in seccion.get("KpisSeccion", []):
                self.assertIn("Nombre", kpi)
                self.assertIn("Tipo_de_KPI", kpi)
                self.assertIn("Task", kpi)
        
        #Segunda vez: debe recuperarlo desde Redis
        cached = redis_client.get(self.redis_key)
        self.assertIsNotNone(cached)

        loaded = json.loads(cached)
        self.assertEqual(loaded["Nombre"], evaluation["Nombre"])
        

class PerformanceTestCase(TestCase):
    def test_performance(self):
        # Datos de ejemplo para la prueba (puedes ajustarlos según tus necesidades)
        tenant_id = 'chasqi'
        evaluation_id = '67b772bfaf33bc64b4d5394c'
        employee_id = '67b61998441df990982006fa'
        start_date = '2025-01-01'
        end_date = '2025-03-31'
        filter_range = 'rango_de_fechas'

        execution_times = []

        for _ in range(10):  # Ejecutar 10 veces para obtener un promedio
            start_time = time.time()
            
            # Llamada a la función que quieres medir el rendimiento
            result = calculate_evaluation_for_employees(
                tenant_id,
                evaluation_id,
                employee_id,
                filter_range,
                start_date,
                end_date
            )
            
            end_time = time.time()
            execution_time = end_time - start_time
            execution_times.append(execution_time)

        # Calcula el promedio del tiempo de ejecución
        average_time = sum(execution_times) / len(execution_times)

        print(f"Tiempo promedio de ejecución: {average_time:.4f} segundos")
        
        # Verifica que el tiempo de ejecución esté por debajo de un umbral razonable (ajústalo a tus necesidades)
        self.assertLess(average_time, 2, "El tiempo de ejecución es demasiado alto")  # Ejemplo de umbral de 2 segundos

        # Asegurarse de que se obtienen resultados válidos
        self.assertIsInstance(result, dict)
        self.assertIn('notas_por_seccion', result)
        self.assertIn('nota_final', result)