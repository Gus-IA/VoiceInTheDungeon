FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./ 
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN mkdir -p /app/data

# Instalar dependencias del backend
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copiar todo el proyecto (backend + frontend estático ya compilado)
COPY . .
COPY --from=frontend-build /app/frontend/static ./frontend/static

EXPOSE 8000

# Render usa el puerto dinámico de la variable $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

