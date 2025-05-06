from django.urls import path
from . import views

urlpatterns = [
    path('count/', views.contar_documentos, name='contar_documentos'),
    path('calculate-evaluation/', views.calcular_evaluacion, name='calcular_evaluacion'),
    path('groupByDepartment/', views.group_by_department, name='group_by_department'),
    path('total-evaluations-department/', views.group_evaluations_by_department, name='group_evaluations_by_department'),
    path('sections-with-kpis/', views.group_secctions_and_kpis, name='group_secctions_and_kpis'),
    path('getEvaluation-realtime-oneEvaluated/', views.get_evaluation_realtime_one_evaluated, name='getEvaluation_realTime_oneEvaluated'),
]