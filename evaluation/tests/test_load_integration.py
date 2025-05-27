import time
import json
from django.test import TestCase, Client

class StressTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/evaluation/webhook/tasklog/"
        self.headers = {
            "HTTP_AUTHORIZATION": "Bearer abc123456789",
            "HTTP_X_TENANT_ID": "chasqi",
        }
        self.payload = {
            "_id": "68226bb3b6756f3d39a73082",
            "TaskId": "67b64b0a441df99098206a4e",
            "colaboradorId": "67b61998441df9909820070c",
            "Record_ID": "77150076970",
            "created_by": "DIANA DEL PILAR CARDENAS RIOS",
            "Activity_assigned_to": "Elizabet Ramirez",
            "hs_create_date": "2025-04-15T18:22:05.327+00:00",
            "hs_activity_date": "2025-04-16T11:00:00.000+00:00",
            "Meeting_outcome": "NO_SHOW",
            "Call_and_meeting_type": "Demo meeting",
            "Ultima_actualizacion": "2025-04-01T18:57:07.366Z",
        }

    def test_load_with_rate_limiting(self):
        total_requests = 15000
        batch_size = 100
        pause_seconds = 60

        for i in range(0, total_requests, batch_size):
            for _ in range(batch_size):
                response = self.client.post(
                    self.url,
                    data=json.dumps(self.payload),
                    content_type="application/json",
                    **self.headers
                )
                self.assertIn(response.status_code, [200, 429, 403])  # Puede bloquear si pasa rate limit
            print(f"Enviados {i + batch_size} registros, esperando {pause_seconds} segundos...")
            time.sleep(pause_seconds)
    
    def test_load_without_pause(self):
        total_requests = 15000
        batch_size = 100

        for i in range(0, total_requests, batch_size):
            for _ in range(batch_size):
                response = self.client.post(
                    self.url,
                    data=json.dumps(self.payload),
                    content_type="application/json",
                    **self.headers
                )
                # Aquí podemos permitir 200, 429 (too many requests) o 403 (forbidden)
                self.assertIn(response.status_code, [200, 429, 403])
            print(f"Enviados {i + batch_size} registros sin pausa...")