from datetime import datetime
from bson import ObjectId
from evaluation.mongo_client import get_collection  # Ajusta el import según tu proyecto

def save_or_update_kpi_evaluation(tenant_id: str, data: dict):
    """
    Guarda o actualiza la evaluación KPI de un empleado para un filtro y rango específico
    usando pymongo y conexión dinámica multi-tenant.
    """

    collection = get_collection(tenant_id, "evaluationhistory")  # O el nombre que uses

    # Construir filtro para buscar documento existente
    filter_query = {
        "employee_id": ObjectId(data.get("employee_id")),
        "evaluacion_id": ObjectId(data.get("evaluacion_id")),
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