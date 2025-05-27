import logging
import json
from bson import ObjectId
from typing import List, Dict, Any, Optional
from evaluation.mongo_client import get_collection
from evaluation.utils.redis_client import redis_client

def get_cached_or_fresh_evaluation(tenant_id, evaluation_id): 
    #1. Buscar en Redis
    key = f"tenant:{tenant_id}:evaluation:{evaluation_id}"
    cached = redis_client.get(key)
    if cached: 
        return json.loads(cached)
    #2. Si no está, traer desde MongoDB
    evaluation_collection = get_collection(tenant_id, 'evaluation')
    kpi_collection = get_collection(tenant_id, 'kpi')

    evaluation = evaluation_collection.find_one(
        {"_id": ObjectId(evaluation_id)},
        {"Nombre": 1, "Evaluados": 1, "Secciones": 1, "Rango_evaluacion": 1, "Dias_no_laborables": 1}
    )
    if not evaluation:
        return None, "Evaluación no encontrada" 
    
    # Paso 3. Obetener todos los KPI Ids y sus datos
    kpi_ids = []
    for seccion in evaluation.get("Secciones", []):
        for k in seccion.get("KpisSeccion", []):
            kpi_ids.append(k["KpiId"])

    unique_kpi_ids = list(set(kpi_ids))
    kpis = kpi_collection.find(
        {"_id": {"$in": unique_kpi_ids}},
        {
            "Nombre": 1,
            "Tipo_de_KPI": 1,
            "Objetivo": 1,
            "Unidad_de_tiempo": 1,
            "Campo_a_evaluar": 1,
            "Formula": 1,
            "Filtro_de_fecha": 1,
            "Filters": 1,
            "Task": 1,
            "Dias_no_laborables": 1
        }
    )

    kpi_map = {
        str(k["_id"]): {
            "_id": str(k["_id"]),
            "Nombre": k.get("Nombre", ""),
            "Tipo_de_KPI": k.get("Tipo_de_KPI", ""),
            "Objetivo": k.get("Objetivo"),
            "Formula": k.get("Formula"),
            "Campo_a_evaluar": k.get("Campo_a_evaluar"),
            "Filtro_de_fecha": k.get("Filtro_de_fecha", "Fecha_de_creacion"),
            "Filters": k.get("Filters", []),
            "Task": k.get("Task", [{}])[0].get("id") if k.get("Task") else None,
            "Dias_no_laborables": k.get("Dias_no_laborables", [])
        }
        for k in kpis
    }

    # 4. Enriquecer cada KPI de cada sección
    for seccion in evaluation.get("Secciones", []):
        for kpi in seccion.get("KpisSeccion", []):
            kpi_id_str = str(kpi["KpiId"])
            kpi_data = kpi_map.get(kpi_id_str, {})
            kpi.update(clean_kpi(kpi_data))

    # 5. Cachear en Redis
    redis_client.setex(key, 21600, json.dumps(evaluation, default=str))
    # 6. Devolver evaluación enriquecida
    return evaluation

def clean_kpi(kpi: dict) -> dict:
    result = {}
    for k, v in kpi.items():
        if v is None or v == []:
            continue
        if k == "Task" and isinstance(v, list) and len(v) > 0 and "id" in v[0]:
            result[k] = v[0]["id"]
        else:
            result[k] = v
    return result

def save_changed_tasklogs(tenant_id: str, payload: dict) -> bool:
    try:
        event = {
            "tenant": tenant_id,
            "payload": payload
        }
        redis_client.lpush('tasklog_events', json.dumps(event))
        return True
    except Exception as e:
        # Aquí podrías loggear el error si quieres rastrear
        print(f"❌ Error al guardar en Redis: {e}")
        return False

