import logging
from pytz import timezone
import pytz
from bson import ObjectId
from evaluation.mongo_client import get_collection
from datetime import timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)
# Zona horaria de Ecuador
Ecuador_tz = pytz.timezone('America/Guayaquil')

def calculate_working_days(start_date, end_date, excluded_days: List[int]) -> (int, int):
    # Asegurarse de que las fechas sean convertidas a la zona horaria de Ecuador
    start_date = start_date.astimezone(Ecuador_tz) if start_date.tzinfo else start_date
    end_date = end_date.astimezone(Ecuador_tz) if end_date.tzinfo else end_date

    # Normalizamos las fechas a las 00:00 para el inicio y 23:59 para el fin en la zona horaria de Ecuador
    start_local = start_date.replace(hour=0, minute=0, second=0)
    end_local = end_date.replace(hour=23, minute=59, second=59)

    days_considered = 0
    non_considered_days = 0
    d = start_local

    # Mapeo de días en Python: 0 = lunes, 1 = martes, ..., 6 = domingo
    # Los días excluidos estarán en la lista 'excluded_days' (0 para lunes, 6 para domingo)
    
    # Calculamos los días laborables y no laborables
    while d <= end_local:
        day_of_week = d.weekday()  # `weekday()` devuelve 0 para lunes, 1 para martes, ..., 6 para domingo
        if day_of_week not in excluded_days:
            days_considered += 1
        else:
            non_considered_days += 1
        d += timedelta(days=1)

    return days_considered, non_considered_days

def apply_kpi_formula(values: List[Any], formula: str) -> float:
    if formula == "count":
        return len(values)
    elif formula == "count_distinct":
        return len(set(values))
    elif formula == "sum":
        numeric_values = []
        for val in values:
            if isinstance(val, str):
                try:
                    val = float(val)
                except ValueError:
                    continue
            if isinstance(val, (int, float)):
                numeric_values.append(val)
        return sum(numeric_values)
    else:
        raise ValueError(f"Invalid KPI formula: {formula}")


def get_kpi_evaluation(task_id: str, kpi_data: Dict[str, Any], tenant_id: str,
                       colaborador_id: str, start_date, end_date) -> Dict[str, Any]:

    task_logs_collection = get_collection(tenant_id, 'tasklog')

    #logger.info("<-----------------Inicia la evaluación de un KPI ------------------------------------------>: %s")

    #logger.info("kpi_data: %s", kpi_data)
    #logger.info("task_id: %s", task_id)
    #logger.info("tenant_id: %s", tenant_id)
    #logger.info("colaborador_id: %s", colaborador_id)
    #logger.info("start_date: %s", start_date)
    #logger.info("end_date: %s", end_date)

    try:
        filter_date = kpi_data.get("Filtro_de_fecha", "Fecha_de_creacion")
        field_to_evaluate = kpi_data["Campo_a_evaluar"]
        formula = kpi_data["Formula"]
        target = float(kpi_data.get("Objetivo", 0))
        unit_time = float(kpi_data.get("Unidad_de_tiempo", 1))

        raw_excluded_days = kpi_data.get("Dias_no_laborables", ["Saturday", "Sunday"])
        day_name_to_index = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6
        }
        excluded_days = [day_name_to_index[d] for d in raw_excluded_days if d in day_name_to_index]
        # Verifica si "Filters" existe y tiene elementos
        if "Filters" in kpi_data and kpi_data["Filters"]:
            dynamic_filters = {f["key"]: f["value"] for f in kpi_data["Filters"] if "key" in f and "value" in f}
        else:
            dynamic_filters = {}
    except KeyError as e:
        raise ValueError(f"Missing required KPI field: {e}")
    

    #logger.info("filter_date: %s", filter_date)
    #ogger.info("field_to_evaluate: %s", field_to_evaluate)
    #logger.info("formula: %s", formula)
    #logger.info("target: %s", target)
    #logger.info("unit_time: %s", unit_time)
    #logger.info("excluded_days: %s", excluded_days)

    # Construir pipeline
    match_stage = {
        "TaskId": ObjectId(task_id),
        "colaboradorId": ObjectId(colaborador_id),
        **dynamic_filters
    }

    if start_date and end_date:
        match_stage[filter_date] = {"$gte": start_date, "$lte": end_date}

    pipeline = [
        {"$match": match_stage},
        #{"$addFields": {
        #    "localDate": {
        #        "$dateToString": {
        #            "format": "%Y-%m-%d",
        #            "date": f"${filter_date}",
        #            "timezone": "America/Guayaquil"
        #        }
        #    },
        #    "dayOfWeek": {
        #        "$dayOfWeek": {
        #            "date": f"${filter_date}",
        #            "timezone": "America/Guayaquil"
        #        }
        #    }
        #}},
        #{"$match": {
        #    "dayOfWeek": {"$nin": excluded_days}
        #}},
        {"$project": {
            field_to_evaluate: 1,
            "colaboradorId": 1,
            "TaskId": 1,
            filter_date: 1
        }}
    ]

    task_logs = list(task_logs_collection.aggregate(pipeline))
    #logger.info("TaskLogs Retrieved: %s", len(task_logs))
    values = [log.get(field_to_evaluate) for log in task_logs if log.get(field_to_evaluate) is not None]

    # Días considerados
    days_considered, non_considered_days = calculate_working_days(start_date, end_date, excluded_days)

    # Meta esperada
    exact_quotient = round(days_considered / unit_time, 2)
    target_sales = round(exact_quotient * target, 2)

    # Resultado
    result_value = apply_kpi_formula(values, formula)
    kpi_percentage = (result_value / target_sales * 100) if target_sales else 0
    rounded_kpi_percentage = round(kpi_percentage, 2)

    #logger.info("<------------------Resultados----------------------------------------------------------->: %s")
    #logger.info("rounded_kpi_percentage: %s", rounded_kpi_percentage)
    #logger.info("result_value: %s", result_value)
    #logger.info("days_considered: %s", days_considered)
    #logger.info("target_sales: %s", target_sales)
    #logger.info("non_considered_days: %s", non_considered_days)

    #logger.info("<-----------------Finaliza la evaluación de un KPI ------------------------------------------>: %s")

    return {
        "kpiPercentage": rounded_kpi_percentage,
        "totalCount": result_value,
        "daysConsidered": days_considered,
        "targetSales": target_sales,
        "nonConsideredDaysCount": non_considered_days
    }