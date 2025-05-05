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