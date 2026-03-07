import pytest
from fastapi.testclient import TestClient
import auth
from main import app, DB_PATH
import sqlite3
import os

client = TestClient(app)

def test_password_hashing():
    password = "secret_password"
    hashed = auth.get_password_hash(password)
    assert hashed != password
    assert auth.verify_password(password, hashed)
    assert not auth.verify_password("wrong_password", hashed)

def test_jwt_token_creation_and_decoding():
    data = {"sub": "testuser"}
    token = auth.create_access_token(data)
    assert token is not None
    
    decoded = auth.decode_access_token(token)
    assert decoded["sub"] == "testuser"

def test_register_and_login_integration():
    # Usar un usuario aleatorio para evitar conflictos si la DB persiste
    import uuid
    username = f"user_{uuid.uuid4().hex[:8]}"
    password = "testpassword123"
    
    # 1. Registro
    resp = client.post("/api/register", json={"username": username, "password": password})
    assert resp.status_code == 200
    assert "éxito" in resp.json()["message"]
    
    # 2. Registro duplicado
    resp = client.post("/api/register", json={"username": username, "password": password})
    assert resp.status_code == 400
    
    # 3. Login exitoso
    # OAuth2PasswordRequestForm usa form data, no JSON directo para el login estándar
    resp = client.post("/api/login", data={"username": username, "password": password})
    assert resp.status_code == 200
    token_data = resp.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    
    # 4. Login fallido
    resp = client.post("/api/login", data={"username": username, "password": "wrongpassword"})
    assert resp.status_code == 401
