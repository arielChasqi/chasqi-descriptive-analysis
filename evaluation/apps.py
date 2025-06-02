from django.apps import AppConfig
import logging

class EvaluationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'evaluation'

    def ready(self):
        from django_celery_beat.models import PeriodicTask, IntervalSchedule
        from django.db.utils import OperationalError, ProgrammingError

        try:
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=1,
                period=IntervalSchedule.MINUTES
            )

            task_name = 'Process tasklogs'

            if not PeriodicTask.objects.filter(name=task_name).exists():
                PeriodicTask.objects.create(
                    interval=schedule,
                    name=task_name,
                    task='evaluation.tasks.process_tasklog_events',
                    enabled=True
                )
                logging.info("✅ Tarea periódica 'Process tasklogs' registrada automáticamente.")
            else:
                logging.info("ℹ️ La tarea periódica 'Process tasklogs' ya existe.")

        except (OperationalError, ProgrammingError):
            logging.warning("⚠️ La tarea periódica no se registró (migraciones no aplicadas aún).")