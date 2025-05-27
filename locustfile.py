from locust import HttpUser, task, between

class TasklogUser(HttpUser):
    wait_time = between(0.01, 0.05)

    @task
    def post_tasklog(self):
        payload = {
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

        headers = {
            "Authorization": "Bearer abc123456789",
            "x-tenant-id": "chasqi",
            "Content-Type": "application/json"
        }

        self.client.post("/evaluation/webhook/tasklog/", json=payload, headers=headers)