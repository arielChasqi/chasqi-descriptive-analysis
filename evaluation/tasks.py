from celery import shared_task
from evaluation.services.services_evaluation_history import save_or_update_kpi_evaluation
import logging
logger = logging.getLogger(__name__)

@shared_task
def save_employee_evaluation_task(tenant_id, data):
    logger.info("Estoy en save_employee_evalaution_task: %s")
    save_or_update_kpi_evaluation(tenant_id, data)