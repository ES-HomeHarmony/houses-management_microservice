import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from app.models import House, Tenents, Issue
from app.routes.tenants_routes import get_tenant_id_via_kafka
from app.schemas import IssueResponse
from datetime import date

# Constantes para valores mock
MOCK_ACCESS_TOKEN = "mock_access_token"
MOCK_TENANT_ID = "test-tenant-id"

MOCK_HOUSE_ID = 1
MOCK_LANDLORD_ID = "test-landlord-id"
MOCK_ISSUE_ID = 1
MOCK_ISSUE_DATA = [
    Issue(
        id=1,
        house_id=1,
        tenant_id=1,
        title="Test Issue 1",
        description="Description for Test Issue 1",
        created_at=date(2025, 1, 2),
        status="open",
        priority="high",
    ),
    Issue(
        id=2,
        house_id=1,
        tenant_id=1,
        title="Test Issue 2",
        description="Description for Test Issue 2",
        created_at=date(2025, 1, 2),
        status="closed",
        priority="medium",
    )
]

MOCK_TENANT = Tenents(
    id=1,
    tenent_id=MOCK_TENANT_ID,
    house_id=1,  # Refers to House.id
    rent=1000.00,
    contract="test-contract",
)

MOCK_HOUSE_DATA = [
    House(
        id=1,
        name="Test House 1",
        landlord_id="test-landlord-id",
        address="123 Test St",
        city="Test City",
        state="TS",
        zipcode="12345",
    ),
    House(
        id=2,
        name="Test House 2",
        landlord_id="test-landlord-id",
        address="456 Another St",
        city="Test City",
        state="TS",
        zipcode="67890",
    ),
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
        
# Test successful tenant ID retrieval
def test_get_tenant_id_via_kafka_success():
    """Test successful tenant ID retrieval from user_cache."""
    with patch("app.routes.tenants_routes.producer.send") as mock_send, \
         patch("app.routes.tenants_routes.user_cache", {"cognito_id": "mock_tenant_id"}), \
         patch("time.sleep", return_value=None) as mock_sleep:
        
        # Mock Kafka producer
        mock_send.return_value.get = MagicMock(return_value="mock_result")

        tenant_id = get_tenant_id_via_kafka("mock_access_token")
        assert tenant_id == "mock_tenant_id"
        mock_send.assert_called_once_with(
            'user-validation-request', value={"action": "validate_token", "access_token": "mock_access_token"}
        )
        mock_sleep.assert_not_called()

# Test Kafka producer exception
def test_get_tenant_id_via_kafka_producer_exception():
    """Test exception handling when Kafka producer fails."""
    with patch("app.routes.tenants_routes.producer.send", side_effect=Exception("Kafka error")), \
         patch("app.routes.tenants_routes.user_cache", {}), \
         patch("time.sleep", return_value=None):

        with pytest.raises(HTTPException) as exc_info:
            get_tenant_id_via_kafka("mock_access_token")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Unauthorized"

# Test createIssue endpoint
def test_create_issue(client_with_access_token, db_session):
    """Test successful issue creation using the test database."""
    # Add a mock tenant to the database
    mock_tenant = Tenents(
        id=1,
        tenent_id=MOCK_TENANT_ID,
        house_id=1,
        rent=1000.00,
        contract="test-contract",
    )
    db_session.add(mock_tenant)
    db_session.commit()

    # Mock Kafka response
    user_cache = {"cognito_id": MOCK_TENANT_ID}
    with patch("app.routes.tenants_routes.user_cache", user_cache):
        # Input data for issue creation
        issue_data = {
            "house_id": 1,
            "title": "Test Issue",
            "description": "Issue description",
            "status": "open",
            "priority": "high",
        }

        # Call the endpoint
        response = client_with_access_token.post("/tenants/createIssue", json=issue_data)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["title"] == "Test Issue"
        assert response_data["description"] == "Issue description"
        assert response_data["status"] == "open"
        assert response_data["priority"] == "high"

# Test createIssue unauthorized access
def test_create_issue_unauthorized(client):
    """Test issue creation without an access token."""
    issue_data = {
        "house_id": 1,
        "title": "Test Issue",
        "description": "Issue description",
        "status": "open",
        "priority": "high",
    }

    # Call the endpoint without access token
    response = client.post("/tenants/createIssue", json=issue_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Access token missing"

# Test createIssue when tenant not found
def test_create_issue_tenant_not_found(client_with_access_token, db_session):
    """Test issue creation when tenant is not found in the database."""
    # Mock Kafka response
    user_cache = {"cognito_id": MOCK_TENANT_ID}
    with patch("app.routes.tenants_routes.user_cache", user_cache):
        # Input data for issue creation
        issue_data = {
            "house_id": 1,
            "title": "Test Issue",
            "description": "Issue description",
            "status": "open",
            "priority": "high",
        }

        # Call the endpoint
        response = client_with_access_token.post("/tenants/createIssue", json=issue_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Tenant not found"

# Test updateIssue endpoint
def test_update_issue(client_with_access_token, db_session, mock_kafka_send):
    """Test successful issue update using the test database."""
    # Add a mock tenant and issue to the database
    mock_tenant = Tenents(
        id=1,
        tenent_id=MOCK_TENANT_ID,
        house_id=1,
        rent=1000.00,
        contract="test-contract",
    )
    mock_issue = Issue(
        id=1,
        house_id=1,
        tenant_id=1,
        title="Original Title",
        description="Original Description",
        status="open",
        priority="medium",
    )
    db_session.add(mock_tenant)
    db_session.add(mock_issue)
    db_session.commit()

    # Mock Kafka response
    user_cache = {"cognito_id": MOCK_TENANT_ID}
    with patch("app.routes.tenants_routes.user_cache", user_cache):
        # Input data for issue update
        update_data = {
            "id": 1,
            "title": "Updated Title",
            "description": "Updated Description",
            "status": "closed",
            "priority": "high",
        }

        # Call the endpoint
        response = client_with_access_token.put("/tenants/updateIssue", json=update_data)
        assert response.status_code == 200
        response_data = response.json()
        assert response_data["title"] == "Updated Title"
        assert response_data["description"] == "Updated Description"
        assert response_data["status"] == "closed"

# Test updateIssue with no access token
def test_update_issue_no_access_token(client):
    """Test issue update without an access token."""
    update_data = {
        "id": 1,
        "title": "Updated Title",
        "description": "Updated Description",
        "status": "closed",
        "priority": "high",
    }

    # Call the endpoint without access token
    response = client.put("/tenants/updateIssue", json=update_data)
    assert response.status_code == 401
    assert response.json()["detail"] == "Access token missing"

# # Test updateIssue when tenant not found
# def test_update_issue_tenant_not_found(client_with_access_token, db_session):
#     """Test issue update when tenant is not found in the database."""
#     # Add mock tenant and issue to the database
#     mock_tenant = Tenents(
#         id=1,
#         tenent_id=MOCK_TENANT_ID,
#         house_id=1,
#         rent=1000.00,
#         contract="test-contract",
#     )
#     mock_issue = Issue(
#         id=1,
#         house_id=1,
#         tenant_id=1,
#         title="Original Title",
#         description="Original Description",
#         status="open",
#         priority="medium",
#     )
#     db_session.add(mock_tenant)
#     db_session.add(mock_issue)
#     db_session.commit()

#     # Mock Kafka response
#     user_cache = {"cognito_id": "different-tenant-id"}
#     with patch("app.routes.tenants_routes.user_cache", user_cache):
#         # Input data for issue update
#         update_data = {
#             "id": 1,
#             "title": "Updated Title",
#             "description": "Updated Description",
#             "status": "closed",
#             "priority": "high",
#         }

#         # Call the endpoint
#         response = client_with_access_token.put("/tenants/updateIssue", json=update_data)
#         assert response.status_code == 404
#         assert response.json()["detail"] == "Tenant not found"

# Test updateIssue when issue not found
def test_update_issue_issue_not_found(client_with_access_token, db_session):
    """Test issue update when issue is not found in the database."""
    # Add mock tenant to the database
    mock_tenant = Tenents(
        id=1,
        tenent_id=MOCK_TENANT_ID,
        house_id=1,
        rent=1000.00,
        contract="test-contract",
    )
    db_session.add(mock_tenant)
    db_session.commit()

    # Mock Kafka response
    user_cache = {"cognito_id": MOCK_TENANT_ID}
    with patch("app.routes.tenants_routes.user_cache", user_cache):
        # Input data for issue update
        update_data = {
            "id": 1,
            "title": "Updated Title",
            "description": "Updated Description",
            "status": "closed",
            "priority": "high",
        }

        # Call the endpoint
        response = client_with_access_token.put("/tenants/updateIssue", json=update_data)
        assert response.status_code == 404
        assert response.json()["detail"] == "Issue not found"

@patch("app.routes.tenants_routes.get_tenant_id_via_kafka")
@patch("sqlalchemy.orm.Session.query")
def test_get_houses_by_tenant_success(mock_query, mock_get_tenant_id, client_with_access_token):
    mock_get_tenant_id.return_value = MOCK_TENANT_ID

    # Mock the sequence of queries
    def query_side_effect(model):
        if model == Tenents:
            # Mock the Tenents query
            mock_tenants_query = MagicMock()
            mock_tenants_query.filter.return_value.all.return_value = [MOCK_TENANT]
            return mock_tenants_query
        elif model == House:
            # Mock the House query
            mock_houses_query = MagicMock()
            mock_houses_query.filter.return_value.all.return_value = MOCK_HOUSE_DATA
            return mock_houses_query
        else:
            raise ValueError("Unexpected query model")

    mock_query.side_effect = query_side_effect

    # Perform the test request
    response = client_with_access_token.get("/tenants/houses")
    assert response.status_code == 200

    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["name"] == "Test House 1"
    assert response_data[1]["name"] == "Test House 2"



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

    # Mock Tenents query to return a list of tenants
    mock_query.side_effect = [
        MagicMock(all=MagicMock(return_value=[MOCK_TENANT])),
        MagicMock(all=MagicMock(return_value=[])),  # No houses
    ]

    response = client_with_access_token.get("/tenants/houses")
    assert response.status_code == 404
    assert response.json()["detail"] == "No houses found for the tenant"

@patch("sqlalchemy.orm.Session.query")
def test_get_issues_by_house(mock_query, client_with_access_token):
    """Test retrieving issues by house ID."""
    # Configurar o mock para retornar objetos Issue
    mock_query.return_value.filter.return_value.all.return_value = MOCK_ISSUE_DATA

    # Depuração: verificar configuração do mock
    print(f"Mock issues: {mock_query.return_value.filter.return_value.all.return_value}")

    # Chamar o endpoint
    response = client_with_access_token.get(f"/tenants/houses/{MOCK_HOUSE_ID}/issues")

    # Depuração: verificar resposta do endpoint
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")

    # Verificar se a resposta está correta
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["title"] == "Test Issue 1"
    assert response_data[1]["title"] == "Test Issue 2"

@patch("sqlalchemy.orm.Session.query")
def test_get_issues_by_house_not_found(mock_query, client_with_access_token):
    """Test retrieving issues when none are found for the house."""
    mock_query.return_value.filter.return_value.all.return_value = []

    response = client_with_access_token.get(f"/tenants/houses/{MOCK_HOUSE_ID}/issues")
    assert response.status_code == 200
    assert response.json() == []

@patch("sqlalchemy.orm.Session.query")
def test_get_issue_by_id(mock_query, client_with_access_token):
    """Test retrieving a specific issue by its ID."""
    mock_query.return_value.filter.return_value.first.return_value = MOCK_ISSUE_DATA[0]

    response = client_with_access_token.get(f"/tenants/issues/{MOCK_ISSUE_ID}")
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["title"] == "Test Issue 1"
    assert response_data["description"] == "Description for Test Issue 1"

@patch("sqlalchemy.orm.Session.query")
def test_get_issue_by_id_not_found(mock_query, client_with_access_token):
    """Test retrieving a specific issue when the issue is not found."""
    mock_query.return_value.filter.return_value.first.return_value = None

    response = client_with_access_token.get(f"/tenants/issues/{MOCK_ISSUE_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"

@patch("sqlalchemy.orm.Session.query")
def test_get_issues_by_landlord(mock_query, client_with_access_token):
    """Test retrieving all issues associated with a landlord."""
    mock_query.return_value.filter.return_value.all.side_effect = [MOCK_HOUSE_DATA, MOCK_ISSUE_DATA]

    response = client_with_access_token.get(f"/tenants/landlords/{MOCK_LANDLORD_ID}/issues")
    assert response.status_code == 200
    response_data = response.json()
    assert len(response_data) == 2
    assert response_data[0]["title"] == "Test Issue 1"

@patch("sqlalchemy.orm.Session.query")
def test_get_issues_by_landlord_no_houses(mock_query, client_with_access_token):
    """Test retrieving issues when the landlord has no houses."""
    mock_query.return_value.filter.return_value.all.side_effect = [[], []]

    response = client_with_access_token.get(f"/tenants/landlords/{MOCK_LANDLORD_ID}/issues")
    assert response.status_code == 404
    assert response.json()["detail"] == f"No houses found for landlord {MOCK_LANDLORD_ID}"

@patch("sqlalchemy.orm.Session.query")
def test_get_issues_by_landlord_no_issues(mock_query, client_with_access_token):
    """Test retrieving issues when the landlord has no issues."""

    mock_query.return_value.filter.return_value.all.side_effect = [MOCK_HOUSE_DATA, []]

    response = client_with_access_token.get(f"/tenants/landlords/{MOCK_LANDLORD_ID}/issues")
    assert response.status_code == 404
    assert response.json()["detail"] == f"No issues found for landlord {MOCK_LANDLORD_ID}"
    


def test_delete_issue(client, db_session):
    """Test deleting an issue by its ID."""
    # Criar e adicionar o mock da instância Issue no banco de testes
    mock_issue = Issue(
        id=MOCK_ISSUE_ID,
        house_id=1,
        tenant_id=1,
        title="Test Issue",
        description="Test Description",
        created_at=date(2025, 1, 2),
        status="open",
        priority="high",
    )
    db_session.add(mock_issue)
    db_session.commit()

    # Verificar se o mock_issue foi persistido no banco
    persisted_issue = db_session.query(Issue).filter(Issue.id == MOCK_ISSUE_ID).first()
    assert persisted_issue is not None

    # Chamar o endpoint para deletar o issue
    response = client.delete(f"tenants/issues/{MOCK_ISSUE_ID}")

    # Verificar a resposta
    assert response.status_code == 200
    assert response.json()["message"] == "Issue deleted successfully"

    # Verificar se o issue foi removido do banco
    deleted_issue = db_session.query(Issue).filter(Issue.id == MOCK_ISSUE_ID).first()
    assert deleted_issue is None

@patch("sqlalchemy.orm.Session.query")
def test_delete_issue_not_found(mock_query, client_with_access_token):
    """Test deleting an issue that does not exist."""
    mock_query.return_value.filter.return_value.first.return_value = None

    response = client_with_access_token.delete(f"/tenants/issues/{MOCK_ISSUE_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Issue not found"