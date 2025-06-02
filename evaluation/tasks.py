import json
import logging
from celery import shared_task
from evaluation.services.services_evaluation_history import ( save_or_update_kpi_evaluation, process_evaluation_for_group) 
from evaluation.utils.redis_client import redis_client
from evaluation.utils.redis_helper import is_event_stale

logger = logging.getLogger(__name__)

@shared_task
def save_employee_evaluation_task(tenant_id, data):
    logger.info("Estoy en save_employee_evalaution_task: %s")
    save_or_update_kpi_evaluation(tenant_id, data)

@shared_task
def process_tasklog_events():
    print("🔁 Procesando eventos tasklog_events...")

    events = redis_client.lrange("tasklog_events", 0, -1)
    print(f"Total eventos en cola: {len(events)}")

    grouped = {}

    for raw_event in events:
        try:
            event = json.loads(raw_event)
            tenant = event.get("tenant")
            payload = json.loads(event["payload"])

            # Preferimos usar Ultima_actualizacion si existe, si no, Fecha_de_creacion
            fecha_str = payload.get("Ultima_actualizacion") or payload.get("Fecha_de_creacion")

            # Verifica que el evento tenga al menos 2 minutos
            if not is_event_stale(fecha_str):
                print("⏳ Evento muy reciente o sin fecha válida. Se omite temporalmente.")
                continue

            task_id = payload.get("TaskId")
            empleado_id = payload.get("colaboradorId")

            if tenant and task_id and empleado_id:
                grouped.setdefault(tenant, {}).setdefault(task_id, {}).setdefault(empleado_id, []).append(payload)

        except Exception as e:
            print(f"❌ Error procesando evento: {e}")

    for tenant_id, tareas in grouped.items():
        for task_id, empleados in tareas.items():
            for colaborador_id, registros in empleados.items():
                try:
                    process_evaluation_for_group(tenant_id, task_id, colaborador_id, registros)
                except Exception as e:
                    print(f"❌ Error al procesar grupo: {e}")

    redis_client.delete("tasklog_events")
    print("✅ Cola de eventos limpiada.")