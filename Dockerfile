# Dockerfile para o FastAPI
FROM python:3.9-slim

WORKDIR /app

# Copiar o ficheiro de requisitos
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY . .

# Expose port
EXPOSE 8000

# Comando para iniciar o FastAPI
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]