from pymongo import MongoClient
from django.conf import settings
from decouple import config  # Importamos config de python-decouple

# Leer la cadena de conexión del archivo .env
db_connection_string = config('DB_CONNECTION_STRING')
print(f"DB_CONNECTION_STRING: {db_connection_string}")  # Imprimir para verificar que se carga correctamente

# Crear la conexión a MongoDB
client = MongoClient(db_connection_string)

def pluralize_tenant(tenant_id):
    if tenant_id.endswith('y') and tenant_id[-2] not in 'aeiou':
        return tenant_id[:-1] + 'ies'
    elif tenant_id.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return tenant_id + 'es'
    else:
        return tenant_id + 's'

def get_collection(tenant_id, collection_base):
    """
    Retorna la colección dinámica basada en el tenant y el tipo de colección.
    
    :param tenant_id: El ID del tenant recibido (ej: 'chasqi', 'bkcompany')
    :param collection_base: El nombre base de la colección (ej: 'tasklog', 'employee')
    :return: Colección de pymongo lista para usar.
    """
    db_name = f"tenant_{tenant_id}"
    plural_tenant = pluralize_tenant(tenant_id)
    collection_name = f"{collection_base}_{plural_tenant}"
    db = client[db_name]

    #print(f"Conectando al client {client} -----------------------------> '")
    #print(f"Conectando al db_name {db_name} con colección 'evaluation'")
    #print(f"Conectando al plural tenant {plural_tenant} con colección 'evaluation'")
    #print(f"Conectando a la colección {collection_name} con colección 'evaluation'")
    #print(f"Conectando a la base de datos {db} con colección 'evaluation'")

    return db[collection_name]