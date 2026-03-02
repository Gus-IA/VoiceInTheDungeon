#!/usr/bin/env bash

set -e

BACKEND_PORT=8000
FRONTEND_PORT=5500

echo "Iniciando backend en http://localhost:${BACKEND_PORT}..."
uvicorn main:app --reload --port "${BACKEND_PORT}" &
BACKEND_PID=$!

echo "Iniciando frontend estático en http://localhost:${FRONTEND_PORT}/index.html..."
python -m http.server "${FRONTEND_PORT}" &
FRONTEND_PID=$!

echo
echo "==========================================="
echo " Backend:  http://localhost:${BACKEND_PORT}/docs"
echo " Frontend: http://localhost:${FRONTEND_PORT}/index.html"
echo "==========================================="
echo "Pulsa Ctrl+C para parar ambos servidores."
echo

trap 'echo "Deteniendo servidores..."; kill ${BACKEND_PID} ${FRONTEND_PID} 2>/dev/null || true; exit 0' INT TERM

wait

