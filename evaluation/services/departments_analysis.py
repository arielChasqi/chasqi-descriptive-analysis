from bson import ObjectId
from evaluation.mongo_client import get_collection

def group_employees_by_department(tenant_id):
    departments_collection = get_collection(tenant_id, 'metadatadepartments')
    employee_collection = get_collection(tenant_id, 'employee')
    user_collection = get_collection(tenant_id, 'user')

    departments = list(departments_collection.find({}, {'Nombre': 1}))
    if not departments:
        return None, "No hay departamentos disponibles"

    dept_name_map = {d['Nombre']: str(d['_id']) for d in departments}

    active_users = list(user_collection.find({"State": "activo"}, {"EmployeeId": 1}))
    active_employee_ids = {u["EmployeeId"] for u in active_users if "EmployeeId" in u}

    empleados = list(employee_collection.find(
        {"_id": {"$in": list(active_employee_ids)}},
        {"Departamento": 1}
    ))

    if not empleados:
        return None, "No hay empleados activos con usuario válido"

    total = len(empleados)
    contador = {}
    for emp in empleados:
        dept_name = emp.get('Departamento') or 'No asignado'
        contador[dept_name] = contador.get(dept_name, 0) + 1

    resultado = sorted([
        {
            "_id": dept_name_map.get(dept, "no-id"),
            "Nombre": dept,
            "numero_empleados": count,
            "porcentaje": round((count / total) * 100, 2)
        }
        for dept, count in contador.items()
    ], key=lambda x: x["numero_empleados"], reverse=True)

    return {
        "message": "Distribución por departamento",
        "total_empleados": total,
        "resultado": resultado
    }, None


def group_employees_by_cargo(tenant_id, department_id):
    departments_collection = get_collection(tenant_id, 'metadatadepartments')
    employee_collection = get_collection(tenant_id, 'employee')
    user_collection = get_collection(tenant_id, 'user')

    dept = departments_collection.find_one({"_id": ObjectId(department_id)})
    if not dept:
        return None, "Departamento no encontrado"

    dept_name = dept.get("Nombre")
    cargos_validos = dept.get("Cargos", [])

    active_users = list(user_collection.find({"State": "activo"}, {"EmployeeId": 1}))
    active_employee_ids = {u["EmployeeId"] for u in active_users if "EmployeeId" in u}

    empleados = list(employee_collection.find(
        {
            "_id": {"$in": list(active_employee_ids)},
            "Departamento": dept_name
        },
        {"Cargo": 1}
    ))

    if not empleados:
        return None, "No hay empleados activos en este departamento"

    total = len(empleados)
    contador = {}
    for emp in empleados:
        cargo = emp.get("Cargo")
        key = cargo if cargo in cargos_validos else "No asignado"
        contador[key] = contador.get(key, 0) + 1

    resultado = sorted([
        {
            "Nombre": cargo,
            "numero_empleados": count,
            "porcentaje": round((count / total) * 100, 2)
        }
        for cargo, count in contador.items()
    ], key=lambda x: x["numero_empleados"], reverse=True)

    return {
        "message": f"Distribución por cargo en '{dept_name}'",
        "departamento": dept_name,
        "total_empleados": total,
        "resultado": resultado
    }, None

def group_evaluations_by_departmentId(tenant_id, department_id):
    departments_collection = get_collection(tenant_id, 'metadatadepartments')
    employee_collection = get_collection(tenant_id, 'employee')
    user_collection = get_collection(tenant_id, 'user')
    evaluations_collection = get_collection(tenant_id, 'evaluation')

    # Validar existencia del departamento
    departamento = departments_collection.find_one(
        {"_id": ObjectId(department_id)},
        {"Nombre": 1}
    )
    if not departamento:
        return None, "Departamento no encontrado"

    dept_name = departamento["Nombre"]

    # Usuarios activos
    active_users = list(user_collection.find({"State": "activo"}, {"EmployeeId": 1}))
    active_employee_ids = {u["EmployeeId"] for u in active_users if "EmployeeId" in u}

    # Empleados activos filtrados por departamento y con evaluaciones
    empleados = list(employee_collection.find(
        {
            "_id": {"$in": list(active_employee_ids)},
            "Departamento": dept_name
        },
        {"Evaluations": 1}
    ))

    if not empleados:
        return None, f"No hay empleados activos con evaluaciones en el departamento '{dept_name}'"

    total = len(empleados)

    # Contar ocurrencias de evaluaciones
    evaluacion_contador = {}
    sin_asignar = 0

    # Clasificar empleados
    for emp in empleados:
        evaluaciones = emp.get("Evaluations", [])
        if evaluaciones:
            for eval_id in evaluaciones:
                eval_id_str = str(eval_id)
                evaluacion_contador[eval_id_str] = evaluacion_contador.get(eval_id_str, 0) + 1
        else:
            sin_asignar += 1

    # Obtener detalles de evaluaciones
    eval_ids = [ObjectId(eid) for eid in evaluacion_contador.keys()]
    evaluaciones = evaluations_collection.find({"_id": {"$in": eval_ids}}, {"Nombre": 1})
    eval_nombre_map = {str(e["_id"]): e.get("Nombre", "Desconocido") for e in evaluaciones}

    # Armar resultado
    resultado = []

    for eval_id, count in evaluacion_contador.items():
        porcentaje = round((count / total) * 100, 2)
        resultado.append({
            "_id": eval_id,
            "Nombre": eval_nombre_map.get(eval_id, "Desconocido"),
            "numero_empleados": count,
            "porcentaje": porcentaje
        })

    # Agregar grupo "Sin asignar"
    if sin_asignar > 0:
        porcentaje = round((sin_asignar / total) * 100, 2)
        resultado.append({
            "_id": "no-id",
            "Nombre": "Sin asignar",
            "numero_empleados": sin_asignar,
            "porcentaje": porcentaje
        })

    # Ordenar descendente
    resultado.sort(key=lambda x: x["numero_empleados"], reverse=True)

    return {
        "total_evaluaciones": len(resultado),
        "total_empleados": total,
        "resultado": resultado
    }, None

def group_secctions_kpis(tenant_id, evaluation_id):
    evaluation_collection = get_collection(tenant_id, 'evaluation')
    kpis_collection = get_collection(tenant_id, 'kpi')

    evaluation = evaluation_collection.find_one({"_id": ObjectId(evaluation_id)})

    return {
        "resultado": "resultado"
    }, None