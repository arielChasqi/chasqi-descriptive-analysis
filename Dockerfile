# Dockerfile
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar e instalar dependencias
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del proyecto
COPY . .

# Expone el puerto en el que corre Django
EXPOSE 3015

# Comando por defecto
CMD ["gunicorn", "descriptive_analysis.wsgi:application", "--bind", "0.0.0.0:3015", "--workers", "4"]
