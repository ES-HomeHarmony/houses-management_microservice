import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from app.models import House, Tenents
from app.routes.tenants_routes import get_tenant_id_via_kafka

# Constantes para valores mock
MOCK_ACCESS_TOKEN = "mock_access_token"
MOCK_TENANT_ID = "test-tenant-id"
MOCK_HOUSE_DATA = [
    House(
        id=1,
        name="Test House 1",
        landlord_id="test-landlord-id",
        address="123 Test St",
        city="Test City",
        state="TS",
        zipcode="12345"
    ),
    House(
        id=2,
        name="Test House 2",
        landlord_id="test-landlord-id",
        address="456 Another St",
        city="Test City",
        state="TS",
        zipcode="67890"
    )
]

# Fixtures
@pytest.fixture
def client_with_access_token(client):
    """Client fixture com token de acesso configurado."""
    client.cookies.set("access_token", MOCK_ACCESS_TOKEN)
    return client

@pytest.fixture
def mock_db_session():
    """Fixture para mock do database session."""
    with patch("sqlalchemy.orm.Session") as mock_session:
        yield mock_session

@pytest.fixture
def mock_kafka_send():
    """Fixture para mock do Kafka producer."""
    with patch("app.routes.tenants_routes.producer.send") as mock_send:
        yield mock_send

# Testes
@patch("app.routes.tenants_routes.get_tenant_id_via_kafka")
@patch("sqlalchemy.orm.Session.query")
def test_get_houses_by_tenant_success(mock_query, mock_get_tenant_id, client_with_access_token):
    mock_get_tenant_id.return_value = MOCK_TENANT_ID
    mock_query.return_value.filter.return_value.first.return_value = Tenents(
        id=1, house_id=1, tenent_id=MOCK_TENANT_ID
    )
    mock_query.return_value.filter.return_value.all.return_value = MOCK_HOUSE_DATA

    response = client_with_access_token.get("/tenants/houses")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Test House 1"
    assert response_data[1]["name"] == "Test House 2"
    mock_get_tenant_id.assert_called_once_with(MOCK_ACCESS_TOKEN)

def test_get_houses_by_tenant_missing_access_token(client):
    """Testa erro ao não fornecer token de acesso."""
    response = client.get("/tenants/houses")
    assert response.status_code == 401
    assert response.json()["detail"] == "Access token missing"

@patch("app.routes.tenants_routes.get_tenant_id_via_kafka")
def test_get_houses_by_tenant_tenant_not_found(mock_get_tenant_id, client_with_access_token, mock_db_session):
    """Testa erro ao não encontrar tenant."""
    mock_get_tenant_id.return_value = MOCK_TENANT_ID
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    response = client_with_access_token.get("/tenants/houses")
    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"
    mock_get_tenant_id.assert_called_once_with(MOCK_ACCESS_TOKEN)

@patch("app.routes.tenants_routes.get_tenant_id_via_kafka")
@patch("sqlalchemy.orm.Session.query")
def test_get_houses_by_tenant_no_houses(mock_query, mock_get_tenant_id, client_with_access_token):
    """Testa erro ao não encontrar casas para o tenant."""
    mock_get_tenant_id.return_value = MOCK_TENANT_ID
    mock_query.return_value.filter.return_value.first.return_value = Tenents(
        id=1, house_id=1, tenent_id=MOCK_TENANT_ID
    )
    mock_query.return_value.filter.return_value.all.return_value = []

    response = client_with_access_token.get("/tenants/houses")
    assert response.status_code == 404
    assert response.json()["detail"] == "No houses found for the tenant"
    mock_get_tenant_id.assert_called_once_with(MOCK_ACCESS_TOKEN)

def test_get_tenant_id_via_kafka_success(mock_kafka_send):
    with patch("app.routes.tenants_routes.tenant_id_cache", {"cognito_id": MOCK_TENANT_ID}):
        mock_kafka_send.return_value = MagicMock()
        mock_kafka_send.return_value.get.return_value = None

        result = get_tenant_id_via_kafka(MOCK_ACCESS_TOKEN)
        assert result == MOCK_TENANT_ID
        mock_kafka_send.assert_called_once_with(
            "user-validation-request", value={"action": "validate_token", "access_token": MOCK_ACCESS_TOKEN}
        )

def test_get_tenant_id_via_kafka_timeout(mock_kafka_send):
    with patch("app.routes.tenants_routes.tenant_id_cache", {}):
        mock_kafka_send.return_value = MagicMock()
        mock_kafka_send.return_value.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_tenant_id_via_kafka(MOCK_ACCESS_TOKEN)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Unauthorized"
        mock_kafka_send.assert_called_once_with(
            "user-validation-request", value={"action": "validate_token", "access_token": MOCK_ACCESS_TOKEN}
        )