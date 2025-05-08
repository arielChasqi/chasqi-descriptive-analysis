from evaluation.services.departments_analysis import get_employees_by_department
from evaluation.services.evaluations_analysis import calculate_evaluation_for_employees
from evaluation.services.evaluations_analysis import get_employees_by_evaluation
from evaluation.services.evaluations_analysis import calculate_evaluation_for_employee

class EvaluationCalculationStrategy:
    def calculate(self, tenant_id, evaluation_id, employee_id=None, department_id=None):
        raise NotImplementedError("Subclasses should implement this method")


class DepartmentBasedEvaluation(EvaluationCalculationStrategy):
    def calculate(self, tenant_id, evaluation_id, employee_id=None, department_id=None):
        print("Using DepartmentBasedEvaluation Strategy")
        # Lógica para recuperar empleados por departamento y calcular evaluación
        employees = get_employees_by_department(tenant_id, department_id)
        return calculate_evaluation_for_employees(tenant_id, evaluation_id, employees)


class EvaluationBasedEvaluation(EvaluationCalculationStrategy):
    def calculate(self, tenant_id, evaluation_id, employee_id=None, department_id=None):
        print("Using EvaluationBasedEvaluation Strategy")
        # Lógica para recuperar empleados asignados a la evaluación y calcular evaluación
        employees = get_employees_by_evaluation(evaluation_id)
        return calculate_evaluation_for_employees(tenant_id, evaluation_id, employees)


class EmployeeBasedEvaluation(EvaluationCalculationStrategy):
    def calculate(self, tenant_id, evaluation_id, employee_id=None, department_id=None):
        print("Using EmployeeBasedEvaluation Strategy")
        # Lógica para calcular la evaluación para un solo empleado
        return calculate_evaluation_for_employee(tenant_id, evaluation_id, employee_id)


class EvaluationContext:
    def __init__(self, strategy: EvaluationCalculationStrategy):
        self._strategy = strategy

    def set_strategy(self, strategy: EvaluationCalculationStrategy):
        self._strategy = strategy

    def calculate(self, tenant_id, evaluation_id, employee_id=None, department_id=None):
        return self._strategy.calculate(tenant_id, evaluation_id, employee_id, department_id)
