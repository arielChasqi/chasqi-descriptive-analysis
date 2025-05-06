import logging
from pytz import timezone
from bson import ObjectId
from evaluation.mongo_client import get_collection
from datetime import timedelta
from typing import List, Dict, Any, Optional

TIMEZONE = timezone("America/Guayaquil")

def calculate_working_days(start_date, end_date, excluded_days: List[int]) -> (int, int):
    start_local = TIMEZONE.localize(start_date).replace(hour=0, minute=0, second=0)
    end_local = TIMEZONE.localize(end_date).replace(hour=23, minute=59, second=59)

    days_considered = 0
    non_considered_days = 0
    d = start_local

    while d <= end_local:
        day_of_week = (d.isoweekday() % 7) + 1  # 1=lunes → 7=domingo
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

    try:
        filter_date = kpi_data.get("Filtro_de_fecha", "Fecha_de_creacion")
        field_to_evaluate = kpi_data["Campo_a_evaluar"]
        formula = kpi_data["Formula"]
        target = float(kpi_data.get("Objetivo", 0))
        unit_time = float(kpi_data.get("Unidad_de_tiempo", 1))
        excluded_days = kpi_data.get("Dias_no_laborables", [1, 7])
        dynamic_filters = {f["key"]: f["value"] for f in kpi_data.get("Filters", [])}
    except KeyError as e:
        raise ValueError(f"Missing required KPI field: {e}")

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
        {"$addFields": {
            "localDate": {
                "$dateToString": {
                    "format": "%Y-%m-%d",
                    "date": f"${filter_date}",
                    "timezone": "America/Guayaquil"
                }
            },
            "dayOfWeek": {
                "$dayOfWeek": {
                    "date": f"${filter_date}",
                    "timezone": "America/Guayaquil"
                }
            }
        }},
        {"$match": {
            "dayOfWeek": {"$nin": excluded_days}
        }},
        {"$project": {
            field_to_evaluate: 1,
            "colaboradorId": 1,
            "TaskId": 1,
            filter_date: 1
        }}
    ]

    task_logs = list(task_logs_collection.aggregate(pipeline))
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

    return {
        "kpiPercentage": rounded_kpi_percentage,
        "totalCount": result_value,
        "daysConsidered": days_considered,
        "targetSales": target_sales,
        "nonConsideredDaysCount": non_considered_days
    }