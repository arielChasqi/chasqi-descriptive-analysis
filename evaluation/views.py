from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from bson import ObjectId

from evaluation.evaluate_strategy.strategy import (
    DepartmentBasedEvaluation,
    EvaluationBasedEvaluation,
    EmployeeBasedEvaluation,
    EvaluationContext
)
  
from evaluation.services.departments_analysis import (
    group_employees_by_department,
    group_employees_by_cargo,
    group_evaluations_by_departmentId,
)

from evaluation.services.evaluations_analysis import group_secctions_kpis

from .mongo_client import get_collection

def contar_documentos(request):
    tenant_id = request.headers.get('x-tenant-id')
    collection_base = request.headers.get('x-collection-base')

    # Validaciones básicas
    if not tenant_id or not collection_base:
        return JsonResponse({"error": "Faltan headers requeridos: x-tenant-id o x-collection-base"}, status=400)

    try:
        collection = get_collection(tenant_id, collection_base)
        total_docs = collection.count_documents({})

        return JsonResponse({
            "tenant": tenant_id,
            "collection": f"{collection_base}_{tenant_id}",
            "total_documents": total_docs
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

@csrf_exempt
def calcular_evaluacion(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa POST"}, status=405)

    try:
        data = json.loads(request.body)
        evaluation_id = data.get('evaluationId')
        tenant_id = data.get('tenantId')
        filter_range = data.get('filterRange')
        start_date_e = data.get('startDateE')
        end_date_e = data.get('endDateE')

        #print(f"Parametro evaluation_id {evaluation_id} con colección 'evaluation'")
        #print(f"Parametro tenant_id {tenant_id} con colección 'evaluation'")

        if not all([evaluation_id, tenant_id, filter_range, start_date_e, end_date_e]):
            return JsonResponse({"error": "Faltan parámetros en la solicitud"}, status=400)

        # Recuperar la colección de evaluaciones
        evaluation_collection = get_collection(tenant_id, 'evaluation')

        # Buscar la evaluación por ID
        evaluation = evaluation_collection.find_one({"_id": ObjectId(evaluation_id)})

        if not evaluation:
            return JsonResponse({"error": "Evaluación no encontrada"}, status=404)

        # Por ahora solo devolvemos la evaluación encontrada
        return JsonResponse({
            "message": "Evaluación recuperada correctamente",
            "evaluation": str(evaluation)  # Temporal, luego formateamos mejor
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

@csrf_exempt
def group_by_department(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa POST"}, status=405)

    try:
        data = json.loads(request.body)
        tenant_id = data.get('tenantId')
        department_id = data.get('departamentId')

        if not tenant_id:
            return JsonResponse({"error": "Falta el parámetro tenantId"}, status=400)

        if department_id:
            response, error = group_employees_by_cargo(tenant_id, department_id)
        else:
            response, error = group_employees_by_department(tenant_id)

        if error:
            return JsonResponse({"error": error}, status=404)

        return JsonResponse(response, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

@csrf_exempt
def group_evaluations_by_department(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa POST"}, status=405)

    try:
        data = json.loads(request.body)
        tenant_id = data.get('tenantId')
        department_id = data.get('departamentId')

        if not tenant_id:
            return JsonResponse({"error": "Falta el parámetro tenantId"}, status=400)

        response, error = group_evaluations_by_departmentId(tenant_id, department_id)
 
        if error:
            return JsonResponse({"error": error}, status=404)

        return JsonResponse(response, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt
def group_secctions_and_kpis(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa POST"}, status=405)

    try:
        data = json.loads(request.body)
        tenant_id = data.get('tenantId')
        evaluation_id = data.get('evaluationId')

        if not tenant_id and not evaluation_id:
            return JsonResponse({"error": "Falta el parámetro tenantId o evaluation_id"}, status=400)

        response, error = group_secctions_kpis(tenant_id, evaluation_id)
 
        if error:
            return JsonResponse({"error": error}, status=404)

        return JsonResponse(response, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt  
def evaluate(request):
    data = json.loads(request.body)
    tenant_id = data.get('tenantId')
    evaluation_id = data.get('evaluationId')
    employee_id = data.get('employeeId', None)
    department_id = data.get('departmentId', None)
    filter_range = data.get('filterRange')
    start_date_str = data.get('startDateE')
    end_date_str = data.get('endDateE')

    # Verifica si los datos llegaron correctamente
    print(f"Tenant ID: {tenant_id}, Evaluation ID: {evaluation_id}, Employee ID: {employee_id}, Department ID: {department_id},Filter Range: {filter_range}, Start Date: {start_date_str}, End Date: {end_date_str}")

    if department_id:
        strategy = DepartmentBasedEvaluation()
    elif employee_id:
        strategy = EmployeeBasedEvaluation()
    else:
        strategy = EvaluationBasedEvaluation()

    context = EvaluationContext(strategy)
    result = context.calculate(tenant_id, filter_range, start_date_str, end_date_str, employee_id, evaluation_id, department_id)

    return JsonResponse(result, safe=False)

@csrf_exempt  # Para evitar error CSRF con llamadas externas
def recibir_tasklog_trigger(request):
    if request.method == "POST":
        data = json.loads(request.body)
        print("✅ Trigger recibido:", data)

        # Acceder a headers
        tenant = request.headers.get('x-tenant-id')
        auth = request.headers.get('authorization')
        print(f"Tenant: {tenant} | Auth: {auth}")

        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "Método no permitido"}, status=405)