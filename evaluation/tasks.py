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

    raw_events = redis_client.lrange("tasklog_events", 0, -1)
    print(f"Total eventos en cola: {len(raw_events)}")

    grouped = {}
    to_keep = []  # Eventos que no deben procesarse aún

    for raw_event in raw_events:
        try:
            event = json.loads(raw_event)
            tenant = event.get("tenant")
            payload = json.loads(event["payload"])

            fecha_str = payload.get("Ultima_actualizacion") or payload.get("Fecha_de_creacion")
            print(f"📅 Fecha del evento: {fecha_str}")

            if not is_event_stale(fecha_str, buffer_minutes=1):  # o 20 luego
                print("⏳ Evento muy reciente. Se mantiene en cola.")
                to_keep.append(raw_event)
                continue

            task_id = payload.get("TaskId")
            empleado_id = payload.get("colaboradorId")

            if tenant and task_id and empleado_id:
                grouped.setdefault(tenant, {}).setdefault(task_id, {}).setdefault(empleado_id, []).append(payload)

        except Exception as e:
            print(f"❌ Error procesando evento: {e}")
            to_keep.append(raw_event)  # En caso de error, no lo pierdas

    # Procesar grupos
    for tenant_id, tareas in grouped.items():
        for task_id, empleados in tareas.items():
            for colaborador_id, registros in empleados.items():
                try:
                    process_evaluation_for_group(tenant_id, task_id, colaborador_id, registros)
                except Exception as e:
                    print(f"❌ Error al procesar grupo: {e}")

    # Limpiar solo lo que ya fue procesado
    redis_client.delete("tasklog_events")
    for ev in to_keep:
        redis_client.rpush("tasklog_events", ev)

    print("✅ Procesamiento finalizado. Eventos recientes se mantienen en cola.")