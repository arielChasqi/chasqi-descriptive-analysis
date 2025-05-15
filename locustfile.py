from locust import HttpUser, task, between

class TasklogUser(HttpUser):
    wait_time = between(0.5, 1)

    @task
    def post_tasklog(self):
        payload = {
            "taskId": "675af3f67e94b212da4e16f6",
            "colaboradorId": "6759f827f200c21186d034f7",
            "fechasEvaluadas": {
                "Ultima_actualizacion": "2025-04-01T18:57:07.366Z",
                "Date_of_Assignment": "2024-12-11T00:00:00.000Z"
            },
            "kpiIds": [
                "67881d8ae700dc4b3791c89f",
                "67a4c6f239c9856e81dfd691"
            ]
        }

        headers = {
            "Authorization": "Bearer abc123456789",
            "x-tenant-id": "chasqi",
            "Content-Type": "application/json"
        }

        self.client.post("/evaluation/webhook/tasklog/", json=payload, headers=headers)