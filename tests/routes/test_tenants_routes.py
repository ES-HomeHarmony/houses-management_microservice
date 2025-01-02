import pytest
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from app.models import House, Tenents, Issue
from app.routes.tenants_routes import get_tenant_id_via_kafka

# Constantes para valores mock
MOCK_ACCESS_TOKEN = "mock_access_token"
MOCK_TENANT_ID = "test-tenant-id"

# Fixtures
@pytest.fixture
def client_with_access_token(client):
    """Client fixture com token de acesso configurado."""
    client.cookies.set("access_token", MOCK_ACCESS_TOKEN)
    return client

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

# Test updateIssue when tenant not found
def test_update_issue_tenant_not_found(client_with_access_token, db_session):
    """Test issue update when tenant is not found in the database."""
    # Add mock tenant and issue to the database
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
    user_cache = {"cognito_id": "different-tenant-id"}
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
        assert response.json()["detail"] == "Tenant not found"

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

# Test updateIssue forbidden access
def test_update_issue_forbidden(client_with_access_token, db_session):
    """Test issue update with forbidden access."""
    # Add mock tenant and issue to the database
    mock_tenant = Tenents(
        id=1,
        tenent_id=MOCK_TENANT_ID,
        house_id=1,
        rent=1000.00,
        contract="test-contract",
    )
    # Issue belongs to a different tenant (unauthorized access)
    mock_issue = Issue(
        id=1,
        house_id=1,
        tenant_id=2,  # Different tenant ID
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
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"