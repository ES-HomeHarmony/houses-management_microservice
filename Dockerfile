# Dockerfile para o FastAPI
FROM python:3.9-slim

WORKDIR /app

# Copiar o ficheiro de requisitos
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY . .

# Configura variáveis de ambiente
ENV DB_USER=admin \
    DB_PASSWORD=adminpassword \
    DB_HOST= \
    DB_NAME=landlord_db \
    DB_PORT=3306 \
    KAFKA_BOOTSTRAP_SERVERS= \
    FRONTEND_URL= \
    AWS_ACCESS_KEY_ID= \
    AWS_SECRET_ACCESS_KEY= \
    S3_BUCKET= \
    S3_REGION=eu-north-1 

# Expose port
EXPOSE 8000

# Comando para iniciar o FastAPI
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]