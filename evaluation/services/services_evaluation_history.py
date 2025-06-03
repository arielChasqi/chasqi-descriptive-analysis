from collections import defaultdict
from datetime import datetime
import json
from bson import ObjectId
from evaluation.mongo_client import get_collection  # Ajusta el import según tu proyecto
from evaluation.services.kpi_calculator import get_kpi_evaluation
from concurrent.futures import ThreadPoolExecutor
import pytz
import logging
from dateutil.parser import parse as parse_date

logger = logging.getLogger(__name__)

LOCAL_TZ = pytz.timezone("America/Guayaquil")

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
    

def normalize_to_local_date(iso_str):
    dt = parse_date(iso_str)
    local_dt = dt.astimezone(LOCAL_TZ)
    return local_dt.date()  # YYYY-MM-DD

def process_task_group(tenant_id, task_id, colaboradores_data):
    print(f"📊 Procesando evaluación: tenant={tenant_id}, task={task_id}")

    # 🔹 Colecciones
    task_collection = get_collection(tenant_id, 'task')
    kpi_collection = get_collection(tenant_id, 'kpi')

    # 🔹 Buscar la tarea y extraer los KPI IDs
    task = task_collection.find_one(
        {"_id": ObjectId(task_id)},
        {"Kpis": 1}
    )
    if not task or "Kpis" not in task:
        print("⚠️ No se encontraron KPIs en la tarea.")
        return

    kpi_ids = [ObjectId(kpi_id) for kpi_id in task["Kpis"]]
    kpis = list(kpi_collection.find(
        {"_id": {"$in": kpi_ids}},
        {"Nombre": 1, "Objetivo": 1, "Formula": 1, 
        "Campo_a_evaluar": 1, "Filtro_de_fecha": 1,
        "Filters": 1, "Dias_no_laborables": 1}
    ))

    # 🔹 Extraer filtros únicos
    filtros_fecha = set()
    for kpi in kpis:
        filtro = kpi.get("Filtro_de_fecha")
        if filtro:
            filtros_fecha.add(filtro)

    print(f"🧪 Filtros únicos: {filtros_fecha}")

     # 🔹 Agrupamiento: {colaborador_id: {fecha: [payloads...]}}
    agrupados = defaultdict(lambda: defaultdict(list))

    # 🔹 Agrupar payloads por colaborador y fecha
    agrupados = defaultdict(lambda: defaultdict(list))
    for colaborador_id, payload in colaboradores_data:
        for filtro in filtros_fecha:
            raw_fecha = payload.get(filtro)
            if not raw_fecha:
                continue
            try:
                fecha_local = normalize_to_local_date(raw_fecha)
                agrupados[colaborador_id][fecha_local].append(payload)
            except Exception as e:
                print(f"❌ Error con fecha '{raw_fecha}': {e}")

    # 🔹 Ejecutar procesamiento por colaborador en paralelo
    def wrapper(colaborador_id):
        sub_agregado = {colaborador_id: agrupados[colaborador_id]}
        return process_kpi_evaluations(tenant_id, task_id, kpis, sub_agregado)

    with ThreadPoolExecutor() as executor:
        all_results = list(executor.map(wrapper, agrupados.keys()))

    print(f"✅ Procesamiento paralelo completo. Total grupos: {len(all_results)}")


def process_kpi_evaluations(tenant_id, task_id, kpis, agrupados):
    trabajos = []

    for colaborador_id, fechas in agrupados.items():
        for fecha, registros in fechas.items():
            start_date = LOCAL_TZ.localize(datetime.combine(fecha, datetime.min.time())).astimezone(pytz.utc)
            end_date = LOCAL_TZ.localize(datetime.combine(fecha, datetime.max.time())).astimezone(pytz.utc)

            trabajos.append((colaborador_id, fecha, start_date, end_date))

    def task_runner(args):
        colaborador_id, fecha, start_date, end_date = args
        return calculate_single_evaluation(
            tenant_id, task_id, colaborador_id, fecha, start_date, end_date, kpis
        )

    with ThreadPoolExecutor() as executor:
        resultados = list(executor.map(task_runner, trabajos))

    return resultados

def calculate_single_evaluation(tenant_id, task_id, colaborador_id, fecha, start_date, end_date, kpis):

    """
    Ejecuta en paralelo las evaluaciones de cada KPI para un colaborador en un rango de fechas.
    """
    def wrapper(kpi_data):
        result = get_kpi_evaluation(task_id, kpi_data, tenant_id, colaborador_id, start_date, end_date)
        print(f"📦 Resultado para KPI {kpi_data.get('nombre')}: {result}")
        return result

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(wrapper, kpis))

    print("🧪 Results (final):", json.dumps(results, indent=2, default=str))

    return results
