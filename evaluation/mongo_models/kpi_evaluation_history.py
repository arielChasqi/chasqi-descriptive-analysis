from mongoengine import Document, ObjectIdField, FloatField, StringField, DateTimeField

class KpiEvaluationHistory(Document):
    employeeId = ObjectIdField(required=True)
    kpiId = ObjectIdField(required=True)
    labelId= StringField("")
    Nota = FloatField()
    Numero_total = FloatField()
    Numero_objetivo = FloatField()
    Numero_faltantes_excedentes = FloatField()
    Fecha_de_inicio = DateTimeField()
    Fecha_de_fin = DateTimeField()
    Numero_de_Dias_laborales = FloatField(1)
    Numero_de_Dias_no_laborales = FloatField(0)
    Fecha_de_creacion = DateTimeField()

    meta = {
        'collection': 'kpi_evaluation_history',
        'indexes': [
            'employeeId',
            'kpiId',
            'Fecha_de_inicio',
            'Fecha_de_fin'
        ]
    }