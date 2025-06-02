from datetime import datetime
from bson import ObjectId
from evaluation.mongo_client import get_collection  # Ajusta el import según tu proyecto
import logging
logger = logging.getLogger(__name__)

def save_or_update_kpi_evaluation(tenant_id: str, data: dict):
    """
    Guarda o actualiza la evaluación KPI de un empleado para un filtro y rango específico
    usando pymongo y conexión dinámica multi-tenant.
    """
    #logger.info("Estoy en save_or_update_kpi_evaluation la función que guarda %s")

    collection = get_collection(tenant_id, "evaluationhistory")  # O el nombre que uses

    # Construir filtro para buscar documento existente
    filter_query = {
        "employee_id": data.get("employee_id"),
        "evaluacion_id": data.get("evaluacion_id"),
        "filter_name": data.get("filter_name"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
    }

    # Actualizar o insertar campo "created_at"
    data["created_at"] = datetime.utcnow()

    # Buscar si ya existe documento
    existing = collection.find_one(filter_query)

    if existing:
        # Actualizar el documento existente
        collection.update_one(filter_query, {"$set": data})
        updated_doc = collection.find_one(filter_query)
        return updated_doc
    else:
        # Insertar nuevo documento
        result = collection.insert_one(data)
        new_doc = collection.find_one({"_id": result.inserted_id})
        return new_doc
    

def process_evaluation_for_group(tenant_id, task_id, colaborador_id, registros):
    # Aquí puedes:
    # - Verificar si ya existe una evaluación
    # - Calcular los KPIs relevantes
    # - Actualizar la nota o estado de cada evaluación
    # - Guardar cambios en MongoDB

    print(f"📊 Procesando evaluación: tenant={tenant_id}, task={task_id}, colaborador={colaborador_id}")
    # TODO: implementar lógica real