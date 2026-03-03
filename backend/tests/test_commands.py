from fastapi.testclient import TestClient

from main import app, ROOMS


client = TestClient(app)


def test_mirar_inicial_describe_habitacion_oscura():
    resp = client.post("/api/command", json={"text": "mirar", "state": None})
    assert resp.status_code == 200
    data = resp.json()
    assert "oscuro" in data["reply"].lower()
    assert data["state"]["room"] == "inicio"


def test_coger_linterna_la_agrega_al_inventario():
    # Partimos del estado inicial
    resp = client.post("/api/command", json={"text": "coger linterna", "state": None})
    assert resp.status_code == 200
    data = resp.json()
    assert "flashlight" in data["state"]["inventory"]


def test_moverse_norte_cambia_de_habitacion():
    state = {"room": "inicio", "inventory": [], "flashlight_on": False}
    resp = client.post("/api/command", json={"text": "ir norte", "state": state})
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"]["room"] == ROOMS["inicio"]["exits"]["norte"]

