from mongoengine import Document, ObjectIdField, FloatField, StringField, ListField, EmbeddedDocument, EmbeddedDocumentField, DateTimeField

class KPINote(EmbeddedDocument):
    kpi_id = ObjectIdField(required=True)
    kpi_name = StringField()
    peso = FloatField()
    nota_kpi = FloatField()
    nota_ponderada = FloatField()
    registros_totales = FloatField()
    metric_objetivo = FloatField()

class KPISection(EmbeddedDocument):
    section_id = ObjectIdField(required=True)
    titulo_seccion = StringField()
    nota_seccion = FloatField()
    nota_ponderada_seccion = FloatField()
    notas_kpis = ListField(EmbeddedDocumentField(KPINote))

class EvaluationHistory(Document):
    employee_id = ObjectIdField(required=True)
    evaluacion_id = ObjectIdField()
    department = StringField()
    cargo = StringField()
    nota_final = FloatField()
    desempenio = StringField()
    color = StringField()
    notas_por_seccion = ListField(EmbeddedDocumentField(KPISection))
    filter_range = StringField()  # Ejemplo: 'ultimo_mes', 'ultimo_trimestre', etc.
    start_date = DateTimeField()
    end_date = DateTimeField()
    created_at = DateTimeField()
    
    meta = {
        'collection': 'kpi_evaluation_history',
        'indexes': [
            'employee_id',
            'evaluacion_id',
            'filter_range',
            ('start_date', 'end_date')
        ]
    }