import logging
from pytz import timezone
from bson import ObjectId
from evaluation.mongo_client import get_collection
from datetime import timedelta
from typing import List, Dict, Any, Optional

def get_evaluation_range_by_percentage(percentage: float, tenant_id: str):
    # Recuperar la colección de MetadataEvaluationrange
    metadata_collection = get_collection(tenant_id, 'metadataevaluationrange')
    
    try:
        # Si el porcentaje es mayor a 100, buscamos el rango con maxValue igual a 100
        if percentage > 100:
            evaluation_range = metadata_collection.find_one({
                "maxValue": 100
            })
        
        # Si el porcentaje es exactamente 100, debe ser el último rango
        elif percentage == 100:
            evaluation_range = metadata_collection.find_one({
                "minValue": {"$lte": percentage},
                "maxValue": {"$eq": 100}  # Exactamente igual a 100
            })
        
        # Caso general: el porcentaje está entre minValue y maxValue
        else:
            evaluation_range = metadata_collection.find_one({
                "minValue": {"$lte": percentage},  # minValue <= porcentaje
                "maxValue": {"$gt": percentage}   # maxValue > porcentaje (excluye el límite superior)
            })
        
        # Si no se encuentra el rango, lanzar un error
        if not evaluation_range:
            raise ValueError("No se encontró un rango para este porcentaje.")
        
        return {
            "title": evaluation_range["title"],
            "color": evaluation_range["color"],
            "minValue": evaluation_range["minValue"],
            "maxValue": evaluation_range["maxValue"]
        }

    except Exception as e:
        # Capturar cualquier error y lanzarlo
        print(f"Error al obtener el rango de evaluación: {e}")
        raise ValueError("Hubo un error al obtener el rango de evaluación.")