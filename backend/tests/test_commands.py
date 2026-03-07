from fastapi.testclient import TestClient

from main import app, ROOMS


client = TestClient(app)

def get_auth_headers():
    # Registrar y loguear un usuario de prueba para obtener el token
    import uuid
    username = f"test_{uuid.uuid4().hex[:6]}"
    client.post("/api/register", json={"username": username, "password": "password123"})
    resp = client.post("/api/login", data={"username": username, "password": "password123"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_mirar_inicial_describe_habitacion_oscura():
    headers = get_auth_headers()
    resp = client.post("/api/command", json={"text": "mirar", "state": None}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "oscuro" in data["reply"].lower()
    assert data["state"]["room"] == "inicio"

def test_coger_linterna_la_agrega_al_inventario():
    headers = get_auth_headers()
    # Partimos del estado inicial
    resp = client.post("/api/command", json={"text": "coger linterna", "state": None}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "flashlight" in data["state"]["inventory"]

def test_moverse_norte_cambia_de_habitacion():
    headers = get_auth_headers()
    state = {"room": "inicio", "inventory": [], "flashlight_on": False}
    resp = client.post("/api/command", json={"text": "ir norte", "state": state}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"]["room"] == ROOMS["inicio"]["exits"]["norte"]

