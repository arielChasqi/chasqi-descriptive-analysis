from evaluation.services.departments_analysis import get_employees_by_department
from evaluation.services.evaluations_analysis import (
    calculate_single_employee_evaluation,
    calculate_evaluation_for_employees,
    calculate_evaluation_for_department
)

class EvaluationCalculationStrategy:
    def calculate(self, tenant_id, filter_range, start_date_str, end_date_str, employee_id=None, evaluation_id=None, department_id=None):
        raise NotImplementedError("Subclasses should implement this method")


class DepartmentBasedEvaluation(EvaluationCalculationStrategy):
    def calculate(self, tenant_id, filter_range, start_date_str, end_date_str, employee_id=None, evaluation_id=None, department_id=None):
        print("Using DepartmentBasedEvaluation Strategy")
        # Lógica para recuperar empleados por departamento y calcular evaluación
        employees = get_employees_by_department(tenant_id, department_id)
        return calculate_evaluation_for_department(tenant_id, employees, filter_range, start_date_str, end_date_str)

class EvaluationBasedEvaluation(EvaluationCalculationStrategy):
    def calculate(self, tenant_id, filter_range, start_date_str, end_date_str, employee_id=None, evaluation_id=None, department_id=None):
        print("Using EvaluationBasedEvaluation Strategy")
        # Lógica para recuperar empleados asignados a la evaluación y calcular evaluación
        return calculate_evaluation_for_employees(tenant_id, evaluation_id, filter_range, start_date_str, end_date_str)

class EmployeeBasedEvaluation(EvaluationCalculationStrategy):
    def calculate(self, tenant_id, filter_range, start_date_str, end_date_str, employee_id=None, evaluation_id=None, department_id=None):
        print("Using EmployeeBasedEvaluation Strategy")
        # Lógica para calcular la evaluación para un solo empleado
        return calculate_single_employee_evaluation(tenant_id, evaluation_id, employee_id, filter_range, start_date_str, end_date_str)

class EvaluationContext:
    def __init__(self, strategy: EvaluationCalculationStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: EvaluationCalculationStrategy):
        self._strategy = strategy

    def calculate(self, tenant_id, filter_range, start_date_str, end_date_str, employee_id=None, evaluation_id=None, department_id=None):
        return self._strategy.calculate(tenant_id, filter_range, start_date_str, end_date_str, employee_id, evaluation_id, department_id)
