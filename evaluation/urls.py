from django.urls import path
from . import views

urlpatterns = [
    path('count/', views.contar_documentos, name='contar_documentos'),
    path('calculate-evaluation/', views.calcular_evaluacion, name='calcular_evaluacion'),
    path('groupByDepartment/', views.group_by_department, name='group_by_department'),
]