import pytest
from app.models import House

# Teste para o endpoint de criação de casa
def test_create_house(client):
    house_data = {
        "name": "Casa de Teste",
        "landlord_id": "landlord123",
        "address": "123 Rua de Teste",
        "city": "TestCity",
        "state": "TS",
        "zipcode": "12345"
    }
    response = client.post("/houses/create", json=house_data)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == house_data["name"]
    assert response_data["landlord_id"] == house_data["landlord_id"]

# Teste para o endpoint de obtenção de casas por landlord
def test_get_houses_by_landlord(client, db_session):
    # Criação de uma casa manualmente no banco de dados para o teste
    house = House(
        name="Casa Teste",
        landlord_id="landlord123",
        address="123 Rua de Teste",
        city="TestCity",
        state="TS",
        zipcode="12345"
    )
    db_session.add(house)
    db_session.commit()

    response = client.get("/houses/landlord/landlord123")
    assert response.status_code == 200
    houses = response.json()
    assert len(houses) > 0
    assert houses[0]["name"] == "Casa Teste"

# Teste para a exceção do endpoint de obtenção de casas por landlord
def test_get_houses_by_landlord_not_found(client):
    response = client.get("/houses/landlord/nonexistent_landlord")
    assert response.status_code == 404
    assert response.json()["detail"] == "Houses not found"