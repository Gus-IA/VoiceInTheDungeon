FROM python:3.12-slim

WORKDIR /app

RUN mkdir -p /app/data

# Instalar dependencias del backend
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar todo el proyecto (backend + frontend estático ya compilado)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

