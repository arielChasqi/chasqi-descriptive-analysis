from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import pytz
from evaluation.services.kpi_calculator import get_kpi_evaluation
from evaluation.mongo_client import get_collection
from evaluation.utils.date_utils import calculate_evaluation_range
from evaluation.services.evaluation_cache import get_cached_or_fresh_evaluation
from evaluation.services.custom_performance import get_evaluation_range_by_percentage


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

#<-------------------------------------------METHOD TO GET EVALUATION COLLABORATORS-------------------------------------------------------------->

def calculate_evaluation_for_employees(tenant_id, evaluation_id, filter_range, start_date_str, end_date_str):
    # Paso 1: Inicializar una lista para los resultados
    resultados = []

    evaluation = get_cached_or_fresh_evaluation(tenant_id, evaluation_id)

    # Extraemos la lista de empleados evaluados directamente de la evaluación cacheada
    evaluados = evaluation.get("Evaluados", [])

     # Si no hay empleados evaluados, retornar un mensaje de error o lista vacía
    if not evaluados:
        logger.error("No se encontraron empleados para evaluar en esta evaluación.")
        return {"error": "No se encontraron empleados para evaluar."}

    logger.info("Empleados a evaluar: %s", evaluados)

    # Paso 1: Calcular fechas según filtro (solo se realiza una vez)
    if filter_range == "rango_de_fechas":
        try:
            start_start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            start_start_date = TIMEZONE.localize(start_start_date).replace(hour=0, minute=0, second=0).astimezone(pytz.utc)

            end_start_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            end_start_date = TIMEZONE.localize(end_start_date).replace(hour=23, minute=59, second=59).astimezone(pytz.utc)
        except ValueError:
            return None, "Fechas inválidas. Usa formato YYYY-MM-DD"
    else:
        rango = calculate_evaluation_range(filter_range, evaluation['Dias_no_laborables'])
        start_start_date = rango["start"]
        end_start_date = rango["end"]

    # Paso 2: Usar ThreadPoolExecutor para paralelizar el cálculo para múltiples empleados
    with ThreadPoolExecutor() as executor:
        resultados = list(executor.map(
            lambda employee: calculate_employee_evaluation(
                tenant_id, evaluation, employee, start_start_date, end_start_date),
            evaluados  # Ahora estamos usando la lista de empleados directamente
        ))

    #Paso 4: Calcular la media de la evaluación
    total_notas = sum(resultado["nota_final"] for resultado in resultados)
    media_evaluacion = round(total_notas / len(resultados), 2) if resultados else 0

    #Paso 5: Calcular la media por sección
    medias_por_seccion = defaultdict(lambda: {"total": 0, "count": 0})

    for resultado in resultados:
        for seccion in resultado.get("notas_por_seccion", []):
            seccion_id = seccion["_id"]
            medias_por_seccion[seccion_id]["total"] += seccion["nota_seccion"]
            medias_por_seccion[seccion_id]["count"] += 1

    # 🔹 6️⃣ Convertir mediasPorSeccion a formato de salida
    promedio_por_seccion = [
        {
            "_id": seccion_id,
            "media": round(seccion_data["total"] / seccion_data["count"], 2)
        }
        for seccion_id, seccion_data in medias_por_seccion.items()
    ]

    # Paso Final: Retornar los resultados
    return {
        "resultados": resultados,
        "start_date": start_start_date.isoformat(),
        "end_date": end_start_date.isoformat(),
        "media_evaluacion": media_evaluacion,  # Media total de todas las evaluaciones
        "promedio_por_seccion": promedio_por_seccion  # Promedio por cada sección
    }

def calculate_employee_evaluation(tenant_id, evaluation, employee_id, start_start_date, end_start_date):
    # Paso 1: Obtener el _id y parametros necesarios del empleado (solo se hace por empleado)
    employee_collection = get_collection(tenant_id, 'employee')
    employee = employee_collection.find_one({"_id": ObjectId(employee_id)}, {"Nombres": 1, "Apellidos": 1, "Departamento": 1, "Cargo": 1, "Area": 1, "Fecha_de_inicio": 1})

    if not employee:
        return None, "No se encontró el colaborador a evaluar con el ID proporcionado."

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

    # 🎯 Nuevo paso: calcular KPIs desde evaluación (usando la evaluación pasada como parámetro)
    resultado_kpis = get_kpis_from_grupal_evaluation(
        evaluation,
        tenant_id,
        employee_id,
        start_start_date,
        end_start_date,
    )

    # Actualizar estructura resultado
    resultado["nota_final"] = resultado_kpis["nota_final"]
    resultado["notas_por_seccion"] = resultado_kpis["notas_por_seccion"]

    # Paso Final: asignar desempeño y color
    try:
        metadata = get_evaluation_range_by_percentage(resultado["nota_final"], tenant_id)
        resultado["desempenio"] = metadata.get("title", "Sin clasificación") if metadata else "Sin clasificación"
        resultado["color"] = metadata.get("color", "#808080") if metadata else "#808080"
    except (TypeError, KeyError, AttributeError) as e:
        logger.warning("Error obteniendo desempeño: %s", str(e))
        resultado["desempenio"] = "Error"
        resultado["color"] = "#FF0000"

    return resultado

def get_kpis_from_grupal_evaluation(evaluation, tenant_id, colaborador_id, start_date, end_date):
    kpievaluationhistory_collection = get_collection(tenant_id, 'kpievaluationhistory')

    # Paso 1: Inicializar variables
    notas_por_seccion = []
    nota_final = 0

    # Paso 2: Recorrer cada sección de la evaluación
    for seccion in evaluation.get("Secciones", []):
        detalles_kpis = []
        nota_seccion = 0  # Inicializamos la variable nota_seccion al principio de cada sección

        # Separar KPIs de tipo evaluación y de tipo métricas
        kpis_tipo_evaluacion = []
        kpis_tipo_metrics = []

        # Recorrer cada KPI de la sección
        for kpi in seccion.get("KpisSeccion", []): 
            kpi_id = str(kpi["KpiId"])
            peso_kpi = kpi.get("Peso", 0)
            label_id = str(kpi.get("Etiqueta")) if kpi.get("Etiqueta") else None
            tipo_kpi = kpi.get("Tipo_de_KPI")

            if tipo_kpi in ["question", "dropdown", "static_metrics"]:
                kpis_tipo_evaluacion.append({
                    "kpi_id": kpi_id,
                    "peso_kpi": peso_kpi,
                    "label_id": label_id,
                    "kpi_info": kpi
                })
            else:
                kpis_tipo_metrics.append({
                    "kpi_id": kpi_id,
                    "peso_kpi": peso_kpi,
                    "kpi_info": kpi
                })

        # Paso 3: Buscar notas en `KPIEvaluationHistory` para los KPIs de tipo evaluación
        if kpis_tipo_evaluacion:
            # Construir el pipeline de agregación para todos los KPIs de tipo evaluación
            pipeline_match = {
                "employeeId": ObjectId(colaborador_id),
                "$or": [
                    {
                        "kpiId": ObjectId(kpi["kpi_id"]),
                        **({"labelId": ObjectId(kpi["label_id"])} if kpi.get("label_id") else {})
                    }
                    for kpi in kpis_tipo_evaluacion
                ]
            }

            pipeline = [
                {"$match": pipeline_match},
                {"$project": {"_id": 0, "kpiId": 1, "labelId": 1, "Nota": 1}}
            ]

            # Ejecutar la agregación para obtener todas las notas de una sola vez
            notas_kpi = list(kpievaluationhistory_collection.aggregate(pipeline))
            # Crear un diccionario de notas por kpiId para una búsqueda rápida
            notas_dict = {str(note["kpiId"]): note for note in notas_kpi}

            # Ahora asignamos las notas a los KPIs correspondientes
            for kpi in kpis_tipo_evaluacion:
                kpi_id = kpi["kpi_id"]
                label_id = kpi.get("label_id")
                peso_kpi = kpi["peso_kpi"]
                info = kpi["kpi_info"]

                # Buscar la nota correspondiente en el diccionario
                nota_kpi_doc = notas_dict.get(str(kpi_id))

                # Si no se encuentra, la nota es 0
                nota_kpi = nota_kpi_doc["Nota"] if nota_kpi_doc else 0
                nota_ponderada = (nota_kpi * peso_kpi) / 100
                nota_seccion += nota_ponderada

                detalles_kpis.append({
                    "_id": kpi_id,
                    "kpi": info.get("Nombre", "Desconocido"),
                    "peso": peso_kpi,
                    "nota_kpi": round(nota_kpi, 2),
                    "nota_ponderada": round(nota_ponderada, 2),
                    "metricObjetivo": info.get("Objetivo")
                })

        # Paso 4: Calcular KPIs de tipo métricas en paralelo usando ThreadPoolExecutor
        if kpis_tipo_metrics:
            with ThreadPoolExecutor() as executor:
                kpi_results = list(executor.map(calculate_kpi_metric, kpis_tipo_metrics, [tenant_id] * len(kpis_tipo_metrics),
                                                [colaborador_id] * len(kpis_tipo_metrics), [start_date] * len(kpis_tipo_metrics),
                                                [end_date] * len(kpis_tipo_metrics)))

            # Filtrar los resultados no nulos y agregar los resultados válidos
            for kpi_result in filter(None, kpi_results):
                detalles_kpis.append(kpi_result)
                nota_seccion += kpi_result["nota_ponderada"]

        # Continuar con el procesamiento del resultado de la sección
        nota_ponderada_seccion = (nota_seccion * seccion.get("PesoSeccion", 0)) / 100
        nota_final += nota_ponderada_seccion

        notas_por_seccion.append({
            "_id": str(seccion["_id"]),
            "titulo_seccion": seccion.get("TituloSeccion", "Sin Título"),
            "nota_seccion": round(nota_seccion, 2),
            "nota_ponderada_seccion": round(nota_ponderada_seccion, 2),
            "notas_kpis": detalles_kpis
        })

    # Paso 6: Retornar los resultados
    return {
        "notas_por_seccion": notas_por_seccion,
        "nota_final": round(nota_final, 2)
    }

#<---------------------------------------METHOD TO GET ONE EMPLOYEE EVALUATION---------------------------------------------------------------->

def calculate_single_employee_evaluation(tenant_id, evaluation_id, employee_id, filter_range, start_date_str, end_date_str):

    #Paso 1. Obtener la evaluación cacheada o desde MongoDB
    evaluation = get_cached_or_fresh_evaluation(tenant_id, evaluation_id)

    if not evaluation:
        return None, "No se encontró la evaluación con el ID proporcionado."
    
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
        rango = calculate_evaluation_range(filter_range, evaluation['Dias_no_laborables'])
        start_start_date = rango["start"]
        end_start_date = rango["end"]

    # Paso 2: Obtener el _id y parametros necesarios del empleado
    employee_collection = get_collection(tenant_id, 'employee')
    employee = employee_collection.find_one({"_id": ObjectId(employee_id)}, {"Nombres": 1, "Apellidos": 1, "Departamento": 1, "Cargo": 1, "Area": 1, "Fecha_de_inicio": 1})

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

    if not employee:
        return None, "No se encontró el colaborador a evaluar con el ID proporcionado."

    # 🎯 Nuevo paso: calcular KPIs desde evaluación
    resultado_kpis = get_kpis_from_evaluation(
        evaluation,
        tenant_id,
        employee_id,
        start_start_date,
        end_start_date,
    )

    # Actualizar estructura resultado
    resultado["nota_final"] = resultado_kpis["nota_final"]
    resultado["notas_por_seccion"] = resultado_kpis["notas_por_seccion"]

     # Paso Final: asignar desempeño y color
    try:
        metadata = get_evaluation_range_by_percentage(resultado["nota_final"], tenant_id)
        resultado["desempenio"] = metadata.get("title", "Sin clasificación") if metadata else "Sin clasificación"
        resultado["color"] = metadata.get("color", "#808080") if metadata else "#808080"
    except (TypeError, KeyError, AttributeError) as e:
        logger.warning("Error obteniendo desempeño: %s", str(e))
        resultado["desempenio"] = "Error"
        resultado["color"] = "#FF0000"

    return resultado

def get_kpis_from_evaluation(evaluation, tenant_id, colaborador_id, start_date, end_date):
    kpievaluationhistory_collection = get_collection(tenant_id, 'kpievaluationhistory')

    # Paso 1: Inicializar variables
    notas_por_seccion = []
    nota_final = 0

    # Paso 2: Recorrer cada sección de la evaluación
    for seccion in evaluation.get("Secciones", []):
        detalles_kpis = []
        nota_seccion = 0  # Inicializamos la variable nota_seccion al principio de cada sección

        # Separar KPIs de tipo evaluación y de tipo métricas
        kpis_tipo_evaluacion = []
        kpis_tipo_metrics = []

        # Recorrer cada KPI de la sección
        for kpi in seccion.get("KpisSeccion", []): 
            kpi_id = str(kpi["KpiId"])
            peso_kpi = kpi.get("Peso", 0)
            label_id = str(kpi.get("Etiqueta")) if kpi.get("Etiqueta") else None
            tipo_kpi = kpi.get("Tipo_de_KPI")

            if tipo_kpi in ["question", "dropdown", "static_metrics"]:
                kpis_tipo_evaluacion.append({
                    "kpi_id": kpi_id,
                    "peso_kpi": peso_kpi,
                    "label_id": label_id,
                    "kpi_info": kpi
                })
            else:
                kpis_tipo_metrics.append({
                    "kpi_id": kpi_id,
                    "peso_kpi": peso_kpi,
                    "kpi_info": kpi
                })

        # Paso 3: Buscar notas en `KPIEvaluationHistory` para los KPIs de tipo evaluación
        if kpis_tipo_evaluacion:
            # Construir el pipeline de agregación para todos los KPIs de tipo evaluación
            pipeline_match = {
                "employeeId": ObjectId(colaborador_id),
                "$or": [
                    {
                        "kpiId": ObjectId(kpi["kpi_id"]),
                        **({"labelId": ObjectId(kpi["label_id"])} if kpi.get("label_id") else {})
                    }
                    for kpi in kpis_tipo_evaluacion
                ]
            }

            pipeline = [
                {"$match": pipeline_match},
                {"$project": {"_id": 0, "kpiId": 1, "labelId": 1, "Nota": 1}}
            ]

            # Ejecutar la agregación para obtener todas las notas de una sola vez
            notas_kpi = list(kpievaluationhistory_collection.aggregate(pipeline))
            # Crear un diccionario de notas por kpiId para una búsqueda rápida
            notas_dict = {str(note["kpiId"]): note for note in notas_kpi}

            # Ahora asignamos las notas a los KPIs correspondientes
            for kpi in kpis_tipo_evaluacion:
                kpi_id = kpi["kpi_id"]
                label_id = kpi.get("label_id")
                peso_kpi = kpi["peso_kpi"]
                info = kpi["kpi_info"]

                # Buscar la nota correspondiente en el diccionario
                nota_kpi_doc = notas_dict.get(str(kpi_id))

                # Si no se encuentra, la nota es 0
                nota_kpi = nota_kpi_doc["Nota"] if nota_kpi_doc else 0
                nota_ponderada = (nota_kpi * peso_kpi) / 100
                nota_seccion += nota_ponderada

                detalles_kpis.append({
                    "_id": kpi_id,
                    "kpi": info.get("Nombre", "Desconocido"),
                    "peso": peso_kpi,
                    "nota_kpi": round(nota_kpi, 2),
                    "nota_ponderada": round(nota_ponderada, 2),
                    "metricObjetivo": info.get("Objetivo")
                })

        # Paso 4: Calcular KPIs de tipo métricas en paralelo usando ThreadPoolExecutor
        if kpis_tipo_metrics:
            with ThreadPoolExecutor() as executor:
                kpi_results = list(executor.map(calculate_kpi_metric, kpis_tipo_metrics, [tenant_id] * len(kpis_tipo_metrics),
                                                [colaborador_id] * len(kpis_tipo_metrics), [start_date] * len(kpis_tipo_metrics),
                                                [end_date] * len(kpis_tipo_metrics)))

            # Filtrar los resultados no nulos y agregar los resultados válidos
            for kpi_result in filter(None, kpi_results):
                detalles_kpis.append(kpi_result)
                nota_seccion += kpi_result["nota_ponderada"]

        # Continuar con el procesamiento del resultado de la sección
        nota_ponderada_seccion = (nota_seccion * seccion.get("PesoSeccion", 0)) / 100
        nota_final += nota_ponderada_seccion

        notas_por_seccion.append({
            "_id": str(seccion["_id"]),
            "titulo_seccion": seccion.get("TituloSeccion", "Sin Título"),
            "nota_seccion": round(nota_seccion, 2),
            "nota_ponderada_seccion": round(nota_ponderada_seccion, 2),
            "notas_kpis": detalles_kpis
        })

    # Paso 6: Retornar los resultados
    return {
        "notas_por_seccion": notas_por_seccion,
        "nota_final": round(nota_final, 2)
    }

def calculate_kpi_metric(kpi, tenant_id, colaborador_id, start_date, end_date):
    info = kpi["kpi_info"]
    task_id = info.get("Task")
    if not task_id:
        return None  # Si no tiene task_id, no se hace nada.

    # Llamamos a la función que calcula el KPI
    kpi_result = get_kpi_evaluation(
        task_id, info, tenant_id, colaborador_id, start_date, end_date
    )

    # Estructuramos el resultado
    return {
        "_id": kpi["kpi_id"],
        "kpi": info.get("Nombre", "Desconocido"),
        "peso": kpi["peso_kpi"],
        "nota_kpi": round(kpi_result["kpiPercentage"], 2),
        "nota_ponderada": round(kpi_result["kpiPercentage"] * kpi["peso_kpi"] / 100, 2),
        "metricObjetivo": kpi_result.get("targetSales")
    }











