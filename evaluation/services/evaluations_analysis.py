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
from evaluation.tasks import save_employee_evaluation_task

TIMEZONE = pytz.timezone("America/Guayaquil")

import logging
logger = logging.getLogger(__name__)

#<----------------------------------------------------------------------------------------------------------------------------------------------->
def search_evaluation_history(data):
     # 1. Intentar buscar evaluación guardada
    collection = get_collection(data.tenant_id, "evaluationhistory")
    doc = collection.find_one({
        "employee_id": data.employee_id,
        "evaluacion_id": data.evaluation_id,
        "filter_name": data.filter_range,
        "start_date": data.start_date,
        "end_date": data.end_date
    })
    
    if doc:
        doc["_id"] = str(doc["_id"])  # Por si necesitas serializar
        return doc

#<----------------------------------------------------------------------------------------------------------------------------------------------->
def employee_evaluations(tenant_id, employee_id):
    employee_collection = get_collection(tenant_id, 'employee')
    evaluation_collection = get_collection(tenant_id, 'evaluation')

    employee = employee_collection.find_one(
        {"_id": ObjectId(employee_id)},
        {"Evaluations": 1}
    )

    if not employee:
        return None, "Empleado no encontrado"

    evaluation_ids = employee.get("Evaluations", [])
    if not evaluation_ids:
        return None, "Este empleado no posee evaluaciones"

    evaluaciones = list(evaluation_collection.find(
        {"_id": {"$in": evaluation_ids}},
        {"Nombre": 1}
    ))

    if not evaluaciones:
        return None, "No se encontraron evaluaciones en la base de datos"

    #logger.info("employee_evaluations %s", evaluation_ids)
    #logger.info("evaluaciones %s", evaluaciones)

     # Convertir ObjectId a str para JSON
    return [
        {"_id": str(ev["_id"]), "Nombre": ev.get("Nombre", "")}
        for ev in evaluaciones
    ], None

#<----------------------------------------------------------------------------------------------------------------------------------------------->
def save_main_employee_evaluation_function(tenant_id, employee_id, evaluation_id):
    employee_collection = get_collection(tenant_id, 'employee')

    employee = employee_collection.find_one(
        {"_id": ObjectId(employee_id)},
        {"Evaluations": 1}
    )

    if not employee:
        return None, "Empleado no encontrado"

    evaluations = employee.get("Evaluations", [])
    if not evaluations:
        return None, "Este empleado no posee evaluaciones"

    eval_oid = ObjectId(evaluation_id)
    if eval_oid not in evaluations:
        return None, "La evaluación no pertenece al empleado"

    # Reordenar: mover al frente
    evaluations.remove(eval_oid)
    evaluations.insert(0, eval_oid)

    # Guardar actualización
    employee_collection.update_one(
        {"_id": ObjectId(employee_id)},
        {"$set": {"Evaluations": evaluations}}
    )

    #logger.info("Evaluación principal actualizada para empleado %s", employee_id)

    return {"status": "Evaluación principal actualizada"}, None

#<----------------------------------------------------------------------------------------------------------------------------------------------->
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
#<--------------------------------------------METHOD TO CALCULATE DATE RANGE--------------------------------------------------------------------->
def define_date_ranges(filter_range, start_date_str, end_date_str, non_working_days_evaluation):
    # Paso 1: Calcular fechas según filtro
    if filter_range == "rango_de_fechas":
        try:
            start_start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            start_start_date = TIMEZONE.localize(start_start_date).replace(hour=0, minute=0, second=0).astimezone(pytz.utc)

            end_start_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            end_start_date = TIMEZONE.localize(end_start_date).replace(hour=23, minute=59, second=59).astimezone(pytz.utc)

            return start_start_date, end_start_date
        
        except ValueError:
            return None, "Fechas inválidas. Usa formato YYYY-MM-DD"
    else:
        rango = calculate_evaluation_range(filter_range, non_working_days_evaluation)
        start_start_date = rango["start"]
        end_start_date = rango["end"]
        return start_start_date, end_start_date

#<-------------------------------------------METHOD TO GET DEPARTMENT EVALUATION----------------------------------------------------------------->

def calculate_evaluation_for_department(tenant_id, employees, filter_range, start_date_str, end_date_str, dept_meta=None):

    evaluations = []  # Lista para almacenar los resultados
    total_score = 0  # Para calcular el promedio del departamento
    total_employees = len(employees)  # Número total de empleados
    employees_by_position = defaultdict(list)  # Diccionario para agrupar empleados por cargo

     # Paso 1: Calcular fechas según filtro (para todos los empleados si es "rango_de_fechas")
    if filter_range == "rango_de_fechas":
        try:
            start_start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            start_start_date = TIMEZONE.localize(start_start_date).replace(hour=0, minute=0, second=0).astimezone(pytz.utc)

            end_start_date = datetime.strptime(end_date_str, "%Y-%m-%d")
            end_start_date = TIMEZONE.localize(end_start_date).replace(hour=23, minute=59, second=59).astimezone(pytz.utc)
        except ValueError:
            return None, "Fechas inválidas. Usa formato YYYY-MM-DD"
    else:
        start_start_date, end_start_date = None, None  # Si no es "rango_de_fechas", cada empleado tiene su propio rango

    # Paso 2: Usar ThreadPoolExecutor para paralelizar el cálculo para múltiples empleados
    with ThreadPoolExecutor() as executor:
        # Paralelizamos el cálculo de evaluación de todos los empleados
        resultados = list(executor.map(
            lambda employee: calculate_single_employee_evaluation_department(
                tenant_id, employee, filter_range, start_start_date, end_start_date
            ),
            employees  # Lista de empleados
        ))

     # Paso 3: Procesamos los resultados
    for resultado in resultados:
        evaluations.append(resultado)
        total_score += resultado["nota_final"]
        # Agrupamos empleados por cargo
        employees_by_position[resultado["cargo"]].append(resultado)

    # Paso 4: Calcular el promedio de notas para cada cargo
    average_by_position = {}
    position_performance = {}

    for position, employees_in_position in employees_by_position.items():
        total_position_score = sum([employee["nota_final"] for employee in employees_in_position])
        avg_score = total_position_score / len(employees_in_position)
        average_by_position[position] = round(avg_score, 2)

        try:
            metadata = get_evaluation_range_by_percentage(avg_score, tenant_id)
            position_performance[position] = {
                "desempenio": metadata.get("title", "Sin clasificación") if metadata else "Sin clasificación",
                "color": metadata.get("color", "#808080") if metadata else "#808080"
            }
        except Exception as e:
            logger.warning("Error obteniendo desempeño de cargo %s: %s", position, str(e))
            position_performance[position] = {
                "desempenio": "Error",
                "color": "#FF0000"
            }

    # Paso 5: Calcular el promedio general del departamento y su desempeño
    department_average = total_score / total_employees if total_employees else 0
    try:
        dept_metadata = get_evaluation_range_by_percentage(department_average, tenant_id)
        department_desempenio = dept_metadata.get("title", "Sin clasificación") if dept_metadata else "Sin clasificación"
        department_color = dept_metadata.get("color", "#808080") if dept_metadata else "#808080"
    except Exception as e:
        logger.warning("Error en desempeño del departamento: %s", str(e))
        department_desempenio = "Error"
        department_color = "#FF0000"

    #Paso 6: Formatear el resultado
    department_result = {
        "_id": dept_meta["_id"] if dept_meta else None,
        "name": dept_meta["name"] if dept_meta else "Desconocido", 
        "average": round(department_average, 2),
        "performance": department_desempenio,
        "color": department_color,
        "totalEmployees": total_employees,
        "sections": []
    }

    for position, employees_in_position in employees_by_position.items():
        section_data = {
            "name": position,
            "average": average_by_position[position],
            "performance": position_performance[position]["desempenio"],
            "color": position_performance[position]["color"],
            "members": []
        }

        for emp in employees_in_position:
            section_data["members"].append({
                "_id": emp["_id"],
                "name": emp["colaborador"],
                "position": emp["cargo"],
                "evaluationId": emp["evaluationId"],
                "evaluation": emp.get("nombreEvaluacion", "Sin nombre"),
                "score": emp["nota_final"],
                "performance": emp["desempenio"],
                "color": emp["color"]
            })

        department_result["sections"].append(section_data)

    return department_result

def calculate_single_employee_evaluation_department(tenant_id, employee, filter_range, start_date_str, end_date_str):
    # Paso 1: Construir estructura de resultado predeterminado
    resultado = {
        "_id": str(employee["_id"]) if isinstance(employee.get("_id"), (str, ObjectId)) else "SIN_ID",
        "colaborador": f"{employee.get('Nombres', '')} {employee.get('Apellidos', '')}",
        "departamento": employee.get("Departamento", "No asignado"),
        "cargo": employee.get("Cargo", "No asignado"),
        "evaluationId": "",
        "nombreEvaluacion": "",
        "nota_final": 0,
        "notas_por_seccion": [],
        "desempenio": "",
        "color": "",
    }

    # Paso 2: Verificamos si el empleado tiene evaluaciones
    if not employee.get("Evaluations"):
        # Si no tiene evaluaciones, devolvemos un resultado predeterminado
        return resultado
    
    # Paso 3. Obtener la evaluación cacheada o desde MongoDB
    evaluation_id = employee["Evaluations"][0]  # Usamos la primera evaluación
    evaluation = get_cached_or_fresh_evaluation(tenant_id, evaluation_id)

    if not evaluation:
        return None, "No se encontró la evaluación con el ID proporcionado."

    # Paso 5: Calcular fechas según filtro
    if filter_range != "rango_de_fechas":
        rango = calculate_evaluation_range(filter_range, evaluation['Dias_no_laborables'])
        start_date_str = rango["start"]
        end_date_str = rango["end"]

    #logger.info("start_start_date: %s", start_date_str)
    #logger.info("end_start_date: %s", end_date_str)

    # : Buscar evaluación guardada
    evaluation_history_collection = get_collection(tenant_id, "evaluationhistory")
    existing = evaluation_history_collection.find_one({
        "employee_id": str(employee["_id"]),
        "evaluacion_id": str(evaluation_id),
        "filter_name": filter_range,
        "start_date": start_date_str,
        "end_date": end_date_str
    })

    if existing:
        evaluation_result = {
        "_id": str(employee["_id"]),
        "evaluation_doc_id": str(existing["_id"]),
        "evaluation_id": str(existing["evaluacion_id"]),
        "colaborador": f"{employee.get('Nombres', '')} {employee.get('Apellidos', '')}",
        "departamento": existing.get("department", "No asignado"),
        "cargo": existing.get("cargo", "No asignado"),
        "nota_final": existing["nota_final"],
        "desempenio": existing["desempenio"],
        "color": existing["color"],
        "evaluationId": str(existing["evaluacion_id"]),
        "nombreEvaluacion": evaluation.get("Nombre", "Sin nombre"),
        }
        return evaluation_result

    # 🎯 Nuevo paso: calcular KPIs desde evaluación
    resultado_kpis = get_kpis_from_evaluation(
        evaluation,
        tenant_id,
        employee["_id"],
        start_date_str,
        end_date_str,
    )

    # Actualizar estructura resultado
    resultado["nota_final"] = resultado_kpis["nota_final"]
    resultado["notas_por_seccion"] = resultado_kpis["notas_por_seccion"]
    resultado["evaluationId"] = str(evaluation["_id"])
    resultado["nombreEvaluacion"] = evaluation.get("Nombre", "Sin nombre")
    # Paso Final: asignar desempeño y color
    try:
        metadata = get_evaluation_range_by_percentage(resultado["nota_final"], tenant_id)
        resultado["desempenio"] = metadata.get("title", "Sin clasificación") if metadata else "Sin clasificación"
        resultado["color"] = metadata.get("color", "#808080") if metadata else "#808080"
    except (TypeError, KeyError, AttributeError) as e:
        logger.warning("Error obteniendo desempeño: %s", str(e))
        resultado["desempenio"] = "Error"
        resultado["color"] = "#FF0000"

    # 🔥 Emitir evento SOLO si el filtro es uno de los cacheables
    CACHEABLE_FILTERS = {"ultimo_mes", "ultimo_trimestre", "ultimo_semestre", "ultimo_anio"}
    if filter_range in CACHEABLE_FILTERS:
    # 🔥 Emitir evento para guardar la evaluación
        save_employee_evaluation_task.delay(tenant_id, {
            "employee_id": str(employee["_id"]),
            "evaluacion_id": str(evaluation["_id"]),
            "department": resultado["departamento"],
            "cargo": resultado["cargo"],
            "nota_final": resultado["nota_final"],
            "desempenio": resultado["desempenio"],
            "color": resultado["color"],
            "notas_por_seccion": resultado["notas_por_seccion"],
            "start_date": start_date_str,
            "end_date": end_date_str,
            "filter_name": filter_range,
        })

    return resultado

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

    #logger.info("Empleados a evaluar: %s", evaluados)

    # Paso 2: Calcular fechas
    start_start_date, end_start_date = define_date_ranges(
        filter_range, start_date_str, end_date_str, evaluation['Dias_no_laborables']
    )

    # Paso 2: Usar ThreadPoolExecutor para paralelizar el cálculo para múltiples empleados
    with ThreadPoolExecutor() as executor:
        resultados = list(executor.map(
            lambda employee: calculate_employee_evaluation(
                tenant_id, evaluation, employee, filter_range, start_start_date, end_start_date),
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

def calculate_employee_evaluation(tenant_id, evaluation, employee_id, filter_range, start_start_date, end_start_date):

    #logger.info("Employee: %s", employee_id)
    #logger.info("filter_range: %s", filter_range)
    #logger.info("start_start_date: %s", start_start_date)
    #logger.info("end_start_date: %s", end_start_date)

    # Paso 1: Buscar evaluación guardada
    evaluation_history_collection = get_collection(tenant_id, "evaluationhistory")
    existing = evaluation_history_collection.find_one({
        "employee_id": employee_id,
        "evaluacion_id": evaluation["_id"],
        "filter_name": filter_range,
        "start_date": start_start_date,
        "end_date": end_start_date
    })

    if existing:
        existing["_id"] = str(existing["_id"])
        return existing  # ⛔️ Aquí devuelves y sales, no calculas más

    # Paso 2: Obtener el _id y parametros necesarios del empleado (solo se hace por empleado)
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

    # 🔥 Emitir evento SOLO si el filtro es uno de los cacheables
    CACHEABLE_FILTERS = {"ultimo_mes", "ultimo_trimestre", "ultimo_semestre", "ultimo_anio"}
    if filter_range in CACHEABLE_FILTERS:
    # 🔥 Emitir evento para guardar la evaluación
        save_employee_evaluation_task.delay(tenant_id, {
            "employee_id": str(employee["_id"]),
            "evaluacion_id": str(evaluation["_id"]),
            "department": resultado["departamento"],
            "cargo": resultado["cargo"],
            "nota_final": resultado["nota_final"],
            "desempenio": resultado["desempenio"],
            "color": resultado["color"],
            "notas_por_seccion": resultado["notas_por_seccion"],
            "start_date": start_start_date,
            "end_date": end_start_date,
            "filter_name": filter_range,
        })

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

    # # Paso 2: Calcular fechas
    start_start_date, end_start_date = define_date_ranges(
        filter_range, start_date_str, end_date_str, evaluation['Dias_no_laborables']
    )

    logger.info("start_date_str: %s", start_start_date)
    logger.info("end_date_str: %s", end_start_date)

    # Paso 3: Buscar evaluación guardada
    evaluation_history_collection = get_collection(tenant_id, "evaluationhistory")
    existing = evaluation_history_collection.find_one({
        "employee_id": employee_id,
        "evaluacion_id": evaluation_id,
        "filter_name": filter_range,
        "start_date": start_start_date,
        "end_date": end_start_date
    })

    if existing:
        existing["_id"] = str(existing["_id"])
        return existing  # ⛔️ Aquí devuelves y sales, no calculas más

    # Paso 4: Obtener el _id y parametros necesarios del empleado
    employee_collection = get_collection(tenant_id, 'employee')
    employee = employee_collection.find_one({"_id": ObjectId(employee_id)}, {"Nombres": 1, "Apellidos": 1, "Departamento": 1, "Cargo": 1, "Area": 1, "Fecha_de_inicio": 1})

    # Paso 5: Construir estructura de resultado
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

    # 🔥 Emitir evento SOLO si el filtro es uno de los cacheables
    CACHEABLE_FILTERS = {"ultimo_mes", "ultimo_trimestre", "ultimo_semestre", "ultimo_anio"}
    if filter_range in CACHEABLE_FILTERS:
        # 🔥 Emitir evento para guardar la evaluación
        save_employee_evaluation_task.delay(tenant_id, {
            "employee_id": str(employee["_id"]),
            "evaluacion_id": str(evaluation_id),
            "department": resultado["departamento"],
            "cargo": resultado["cargo"],
            "nota_final": resultado["nota_final"],
            "desempenio": resultado["desempenio"],
            "color": resultado["color"],
            "notas_por_seccion": resultado["notas_por_seccion"],
            "start_date": start_start_date,
            "end_date": end_start_date,
            "filter_name": filter_range,
        })
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
        "registros_totales": kpi_result["totalCount"],
        "metricObjetivo": kpi_result.get("targetSales")
    }











