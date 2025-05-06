from datetime import datetime
from bson import ObjectId
import pytz
from evaluation.mongo_client import get_collection
from evaluation.utils.date_utils import calculate_evaluation_range

TIMEZONE = pytz.timezone("America/Guayaquil")

import logging
logger = logging.getLogger(__name__)

def group_secctions_kpis(tenant_id, evaluation_id):
    evaluation_collection = get_collection(tenant_id, 'evaluation')
    kpis_collection = get_collection(tenant_id, 'kpi')

    #1. Buscar evaluaciones y secciones
    evaluation = evaluation_collection.find_one({"_id": ObjectId(evaluation_id)}, {"Secciones": 1})

    if not evaluation or not evaluation.get("Secciones"):
        return None, "Evaluación no encontrada o sin secciones"
    
    secciones= evaluation["Secciones"]

    #2. Extraer todos los IDs de KPI en todas las secciones
    all_kpi_ids = []
    for seccion in secciones: 
        kpi_ids = [k["KpiId"] for k in seccion.get("KpisSeccion", [])]
        all_kpi_ids.extend(kpi_ids)

    #3. Buscar detalles de los KPI únicos
    unique_kpi_ids = list(set(all_kpi_ids))
    kpis = kpis_collection.find({"_id": {"$in": unique_kpi_ids}}, {"Nombre": 1})

    #logger.info("KPI IDs únicos obtenidos: %s", unique_kpi_ids)

    kpi_map = {str(k["_id"]): k["Nombre"] for k in kpis}

    #logger.debug("Map de KPIs: %s", kpi_map)

    #4. Contruir resultado
    resultado = []
    for seccion in secciones:
        kpis_data = []
        for kpi in seccion.get("KpisSeccion", []):
            kpi_id = str(kpi.get("KpiId"))
            kpis_data.append({
               "_id": kpi_id,
                "Nombre": kpi_map.get(kpi_id, "Desconocido"),
                "Peso": kpi.get("Peso", 0)     
            })

        resultado.append({
            "_id": str(seccion.get("_id")),
            "Titulo": seccion.get("TituloSeccion", "Sin título"),
            "Peso": seccion.get("PesoSeccion", 0),
            "Kpis": kpis_data
        })

    return {
        "resultado": resultado
    }, None

def getEvaluation_real_time_one_evaluated(tenant_id, evaluation_id, employee_id, filter_range, start_date_str, end_date_str):
    evaluation_collection = get_collection(tenant_id, 'evaluation')
    kpi_collection = get_collection(tenant_id, 'kpi')
    employee_collection = get_collection(tenant_id, 'employee')

    # Paso 0: Obtener evaluación
    evaluation = evaluation_collection.find_one({"_id": ObjectId(evaluation_id)})
    if not evaluation:
        return None, "Evaluación no encontrada"

    dias_no_laborables = evaluation.get("Dias_no_laborables", [])

    # Paso 1: Calcular fechas según filtro
    if filter_range == "rango_de_fechas":
        try:
            start_start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            start_start_date = TIMEZONE.localize(start_start_date).replace(hour=0, minute=0, second=0).astimezone(pytz.utc)

            end_start_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            end_start_date = TIMEZONE.localize(end_start_date).replace(hour=23, minute=59, second=59).astimezone(pytz.utc)
        except ValueError:
            return None, "Fechas inválidas. Usa formato YYYY-MM-DD"
    else:
        rango = calculate_evaluation_range(filter_range, dias_no_laborables)
        start_start_date = rango["start"]
        end_start_date = rango["end"]

    # Paso 2: Obtener el _id y paràmetros necesarios del empleado
    employee = employee_collection.find_one({"_id": ObjectId(employee_id)}, {"Nombres": 1, "Apellidos": 1, "Departamento": 1, "Area": 1, "Fecha_de_inicio": 1})
    
    if not employee:
        return None, "Evaluado no encontrado"
    
   # Paso 3: Construir estructura de resultado
    resultado = {
        "_id": str(employee["_id"]),
        "colaborador": f"{employee.get('Nombres', '')} {employee.get('Apellidos', '')}",
        "departamento": employee.get("Departamento", "No asignado"),
        "cargo": employee.get("Cargo", "No asignado"),
        "nota_final": 0,
        "desempenio": "",
        "color": "",
        "notas_por_seccion": []
    }

    # Paso 4: Obtener mapa de KPIs usados en la evaluación
    kpi_ids = []
    for seccion in evaluation.get("Secciones", []):
        kpi_ids.extend([k["KpiId"] for k in seccion.get("KpisSeccion", [])])

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
            "Dias_no_laborables": k.get("Dias_no_laborables", [])
        }
        for k in kpis
    }




    return {
        "fecha_inicio": start_start_date.isoformat(),
        "fecha_fin": end_start_date.isoformat(),
        "dias_no_laborables": dias_no_laborables,
        "evaluacion": {
            "_id": str(evaluation["_id"]),
            "Nombre": evaluation.get("Nombre", "Sin nombre")
        },
        "evaluado": resultado,
        "kpis": kpi_map  # opcional: puedes devolverlo para debug
    }, None


