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

from evaluation.services.evaluations_analysis import (
    group_secctions_kpis,
    employee_evaluations,
    save_main_employee_evaluation_function,
    get_timeline_employee_evaluation
)

@csrf_exempt
def group_by_department(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa POST"}, status=405)

    try:
        tenant_id = request.headers.get('x-tenant-id')
        data = json.loads(request.body)
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
        tenant_id = request.headers.get('x-tenant-id')
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
        tenant_id = request.headers.get('x-tenant-id')
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
def timeline_employee_evaluation(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa POST"}, status=405)

    try:
        data = json.loads(request.body)
        tenant_id = request.headers.get('x-tenant-id')
        evaluation_id = data.get('evaluationId')
        employee_id = data.get('employeeId')
        filter_range = data.get('filterRange')
        number_of_data = data.get('numberOfData')

        if not tenant_id or not evaluation_id or not employee_id or not filter_range:
            return JsonResponse({"error": "Falta parámetros para realizar la gráfica TimeLine"}, status=400)

        response, error = get_timeline_employee_evaluation(tenant_id, evaluation_id, employee_id, filter_range, number_of_data)
 
        if error:
            return JsonResponse({"error": error}, status=404)

        return JsonResponse(response, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    
@csrf_exempt  
def evaluate(request):
    tenant_id = request.headers.get('x-tenant-id')
    data = json.loads(request.body)
    evaluation_id = data.get('evaluationId', None)
    employee_id = data.get('employeeId', None)
    department_id = data.get('departmentId', None)
    filter_range = data.get('filterRange')
    start_date_str = data.get('startDateE', None)
    end_date_str = data.get('endDateE', None)

    if not tenant_id:
        return JsonResponse({"error": "Falta el parámetro tenantId"}, status=400)

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

@csrf_exempt
def get_employee_evaluations(request):
    if request.method != 'GET':
        return JsonResponse({"error": "Método no permitido, usa GET"}, status=405)

    try: 
        tenant_id = request.headers.get('x-tenant-id')
        employee_id = request.GET.get('employeeId')

        if not tenant_id or not employee_id:
            return JsonResponse({"error":  "Falta el parámetro tenantId o employeeId"}, status=400)
        
        response, error = employee_evaluations(tenant_id, employee_id)

        if error: 
            return JsonResponse({"error": error}, status=404) 
        
        return JsonResponse(response, safe=False)
        
    except Exception as e: 
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def save_main_employee_evaluation(request):
    if request.method != 'POST':
        return JsonResponse({"error": "Método no permitido, usa GET"}, status=405)

    try: 
        tenant_id = request.headers.get('x-tenant-id')
        data = json.loads(request.body)
        employee_id = data.get('employeeId', None)
        evaluation_id = data.get('evaluationId', None)

        if not tenant_id or not employee_id or not evaluation_id:
            return JsonResponse({"error":  "Falta el parámetro tenantId, employeeId o evaluation_id"}, status=400)
        
        response, error = save_main_employee_evaluation_function(tenant_id, employee_id, evaluation_id)

        if error: 
            return JsonResponse({"error": error}, status=404) 
        
        return JsonResponse(response, safe=False)
        
    except Exception as e: 
        return JsonResponse({"error": str(e)}, status=500)

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
