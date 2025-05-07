from datetime import datetime
from bson import ObjectId
import pytz
from evaluation.services.kpi_calculator import get_kpi_evaluation
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
            "Task": k.get("Task", []),
            "Dias_no_laborables": k.get("Dias_no_laborables", [])
        }
        for k in kpis
    }

    # Paso 5: Obtener los KPIs de cada seccion y calcular resultados


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

def get_kpis_from_evaluation(evaluation, tenant_Id, colaborador_Id, start_date, end_date, kpi_map):
    kpievaluationhistory_collection = get_collection(tenant_Id, 'kpievaluationhistory')

    # Paso 1: Inicializar variables
    notas_por_seccion = []
    nota_final = 0

    # Paso 2: Recorrer cada sección de la evaluación
    for seccion in evaluation.get("Secciones", []):
        detalles_kpis = []
        nota_seccion = 0

        #Separar KPIs de tipo evaluacion y de tipo métricas
        kpis_tipo_evaluacion = []
        kpis_tipo_metrics = []

        #Recorrer cada KPI de la seccion
        for kpi in seccion.get("KpisSeccion", []): 
            kpi_id = str(kpi["KpiId"])
            peso_kpi = kpi.get("Peso", 0)
            label_id = str(kpi.get("Etiqueta")) if kpi.get("Etiqueta") else None
            kpi_data = kpi_map.get(kpi_id)

            if not kpi_data:
                print(f"⚠️ KPI no encontrado: {kpi_id}")
                continue
            
            #Separar por tipo de KPI
            if kpi_data["Tipo_de_KPI"] in ["question", "dropdown", "static_metrics"]:
                kpis_tipo_evaluacion.append({"kpi_id": kpi_id, "peso_kpi": peso_kpi, "label_id": label_id})
            else:
                kpis_tipo_metrics.append({"kpi_id": kpi_id, "peso_kpi": peso_kpi})

        # Paso 3: Buscar notas en `KPIEvaluationHistory` para los KPIs de tipo evaluación
        if kpis_tipo_evaluacion:
            # Construir el pipeline de agregación
            pipeline_match = {
                "employeeId": ObjectId(colaborador_Id),
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

            # Ejecutar agregación para obtener las notas
            notas_kpi = list(kpievaluationhistory_collection.aggregate(pipeline))

            # Asignar notas a los KPIs
            for kpi in kpis_tipo_evaluacion:
                kpi_id = kpi["kpi_id"]
                label_id = kpi.get("label_id")
                peso_kpi = kpi["peso_kpi"]

                # Buscar la nota correspondiente
                nota_kpi_doc = next(
                    (n for n in notas_kpi if str(n["kpiId"]) == kpi_id and
                     (not label_id or str(n.get("labelId")) == label_id)), None)

                # Si no se encuentra, la nota es 0
                nota_kpi = nota_kpi_doc["Nota"] if nota_kpi_doc else 0
                nota_ponderada = (nota_kpi * peso_kpi) / 100
                nota_seccion += nota_ponderada

                # Agregar detalle del KPI
                detalles_kpis.append({
                    "_id": kpi_id,
                    "kpi": kpi_map.get(kpi_id, {}).get("Nombre", "Desconocido"),
                    "peso": peso_kpi,
                    "nota_kpi": round(nota_kpi, 2),
                    "nota_ponderada": round(nota_ponderada, 2),
                    "metricObjetivo": kpi_map.get(kpi_id, {}).get("Objetivo")
                })

         # Paso 4: Calcular KPIs de tipo métricas
        if kpis_tipo_metrics:
            for kpi in kpis_tipo_metrics:
                kpi_data = kpi_map.get(kpi["kpi_id"])
                task_id = kpi_data.get("Task", [{}])[0].get("id")
                if not task_id:
                    continue

                # Llamar a la función que calcula el KPI (en vez de un servicio externo)
                #kpi_result = get_kpi_evaluation(
                #    task_id, kpi_data, tenant_id, colaborador_id, start_date, end_date
                #)

                # Agregar el resultado al cálculo de la sección
                #detalles_kpis.append({
                #    "_id": kpi["kpi_id"],
                #    "kpi": kpi_data["Nombre"],
                #    "peso": kpi["peso_kpi"],
                #    "nota_kpi": round(kpi_result["kpiPercentage"], 2),
                #    "nota_ponderada": round(kpi_result["kpiPercentage"] * kpi["peso_kpi"] / 100, 2),
                #    "metricObjetivo": kpi_result["targetSales"]
                #})

                # Acumulamos la nota ponderada en la sección
                #nota_seccion += round(kpi_result["kpiPercentage"] * kpi["peso_kpi"] / 100, 2)

        # Paso 5: Finalizar la sección
        notas_por_seccion.append({
            "_id": str(seccion["_id"]),
            "titulo_seccion": seccion.get("TituloSeccion", "Sin Título"),
            "nota_seccion": round(nota_seccion, 2),
            "notas_kpis": detalles_kpis
        })

        # Sumar la nota ponderada de la sección al total de la evaluación
        nota_ponderada_seccion = (nota_seccion * seccion.get("PesoSeccion", 0)) / 100
        nota_final += nota_ponderada_seccion

    # Paso 6: Retornar los resultados
    return {
        "notas_por_seccion": notas_por_seccion,
        "nota_final": round(nota_final, 2)
    }

