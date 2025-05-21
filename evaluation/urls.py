from django.urls import path
from . import views

urlpatterns = [
    path('groupByDepartment/', views.group_by_department, name='group_by_department'),
    path('total-evaluations-department/', views.group_evaluations_by_department, name='group_evaluations_by_department'),
    path('sections-with-kpis/', views.group_secctions_and_kpis, name='group_secctions_and_kpis'),
    path('evaluate/', views.evaluate, name='evaluate'),
    path('get-employee-evaluations', views.get_employee_evaluations, name='get-employee-evaluations'),
    path('save-main-evaluation/', views.save_main_employee_evaluation, name='save-main-employee-evaluation'),
    path('webhook/tasklog/', views.recibir_tasklog_trigger, name='recibir_tasklog_trigger'),
]