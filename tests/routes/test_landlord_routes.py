from cmath import isclose
import pytest
from fastapi import HTTPException
from app.models import Expense, House, TenantExpense, Tenents
from app.routes.landlords_routes import get_landlord_id_via_kafka, create_user_in_user_microservice,create_tenant_expenses
from unittest.mock import patch, MagicMock, call
from botocore.exceptions import NoCredentialsError
from datetime import datetime
import json
from app.database import Base, engine
# Define the data to be sent in the POST request
house_data = {
    "name": "Test House",
    "landlord_id": "test-landlord-id",
    "address": "123 Test St",
    "city": "Test City",
    "state": "TS",
    "zipcode": "12345"
}

# Mock data for the test
create_expense = {
    "house_id": 1,
    "amount": 1000.0,
    "title": "Rent",
    "description": "Monthly rent",
    "deadline_date": "2021-10-01",
}

@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Set up and clean up the test database for each test."""
    Base.metadata.create_all(bind=engine)  # Cria as tabelas antes de cada teste
    yield
    Base.metadata.drop_all(bind=engine)  # Remove as tabelas após o teste

# Sample test file data
def generate_mock_file():
    file_content = b"Test content of the file"
    return {"file": ("test_file.pdf", file_content, "application/pdf")}

@pytest.fixture
def mock_s3_client():
    # Ensure the patch matches the module where boto3.client is called
    with patch("app.routes.landlords_routes.s3_client") as mock_client:
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        yield mock_s3

# Mock test for the house creation endpoint
@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_create_house(mock_get_landlord, client):
    
    mock_get_landlord.return_value = "test-landlord-id"  # Simulate successful response

    # Simulate an access token in the cookies
    access_token = "mock_access_token"

    # Send a POST request to the create endpoint with the access token in cookies
    client.cookies.set("access_token", access_token)
    response = client.post(
        "/houses/create",
        json=house_data
    )

    # Assertions to verify behavior
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == house_data["name"]
    assert response_data["landlord_id"] == house_data["landlord_id"]

    # Verify that the get_landlord_id_via_kafka function was called with the correct access token
    mock_get_landlord.assert_called_once_with(access_token)


def test_create_house_missing_access_token(client):
    # Send a POST request to the create endpoint with missing data
    response = client.post(
        "/houses/create",
        json=house_data
    )

    # Assertions to verify behavior
    assert response.status_code == 401
    assert response.json()["detail"] == "Access token missing"

@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_create_house_by_landlord_not_found(mocked_cognito_id, client):
    
    mocked_cognito_id.return_value = None

    # Simulate an access token in the cookies
    access_token = "mock-access-token"

    # Send a GET request to the landlord endpoint with the access token in cookies
    client.cookies.set("access_token", access_token)
    response = client.post(
        "/houses/create",
        json=house_data
    )

    # Assertions to verify behavior
    assert response.status_code == 404
    assert response.json()["detail"] == "Landlord not found or unauthorized"

    # Verify that the get_landlord_id_via_kafka function was called with the correct access token
    mocked_cognito_id.assert_called_once_with(access_token)


@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_get_houses_by_landlord(mock_get_landlord, client):
    
    house_list = [
        House(
            id=1,
            name="House 1",
            landlord_id="test-landlord-id",
            address="123 Test St",
            city="Test City",
            state="TS",
            zipcode="12345"
        ),
        House(
            id=2,
            name="House 2",
            landlord_id="test-landlord-id",
            address="456 Another St",
            city="Test City",
            state="TS",
            zipcode="67890"
        )
    ]

    mock_get_landlord.return_value = "test-landlord-id"
    access_token = "mock_access_token"

    with patch("sqlalchemy.orm.Query.all", return_value=house_list):
        client.cookies.set("access_token", access_token)
        response = client.get("/houses/landlord")

        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 2
        assert response_data[0]["name"] == "House 1"
        assert response_data[1]["name"] == "House 2"
        mock_get_landlord.assert_called_once_with(access_token)

def test_get_houses_by_landloard_missing_access_token(client):
    # Send a POST request to the create endpoint with missing data
    response = client.get(
        "/houses/landlord"
    )

    # Assertions to verify behavior
    assert response.status_code == 401
    assert response.json()["detail"] == "Access token missing"

@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_get_houses_by_landlord_not_found(mocked_cognito_id, client):
    
    mocked_cognito_id.return_value = None

    # Simulate an access token in the cookies
    access_token = "mock-access-token"

    # Send a GET request to the landlord endpoint with the access token in cookies
    client.cookies.set("access_token", access_token)
    response = client.get(
        "/houses/landlord"
    )

    # Assertions to verify behavior
    assert response.status_code == 404
    assert response.json()["detail"] == "Landlord not found or unauthorized"

    # Verify that the get_landlord_id_via_kafka function was called with the correct access token
    mocked_cognito_id.assert_called_once_with(access_token)

# Mock test for getting houses by landlord endpoint
@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_get_houses_by_landlord_with_no_houses(mock_get_landlord, client):
    
    # Sample data for house retrieval
    house_list = []

    # Simulate an access token in the cookies
    access_token = "mock_access_token"

    # Configure the mock to return a specific landlord ID
    mock_get_landlord.return_value = "test-landlord-id"

    # Mock database session query
    with patch("sqlalchemy.orm.Query.all", return_value=house_list):
        # Send a GET request to the landlord endpoint with the access token in cookies
        client.cookies.set("access_token", access_token)
        response = client.get(
            "/houses/landlord"
        )

        # Assertions to verify behavior
        assert response.status_code == 404
        assert response.json()["detail"] == "Houses not found"

        # Verify that the get_landlord_id_via_kafka function was called with the correct access token
        mock_get_landlord.assert_called_once_with(access_token)

# Test for the get_landlord_id_via_kafka function
def test_get_landlord_id_via_kafka():
    access_token = "mock_access_token"

    # Patch the Kafka producer and user cache
    with patch("app.routes.landlords_routes.producer.send") as mock_send, \
         patch("app.routes.landlords_routes.user_cache", {"cognito_id": "test-landlord-id"}):

        # Simulate the Kafka send function
        mock_send.return_value = MagicMock()
        mock_send.return_value.get.return_value = None  # Simulate successful send

        # Call the function
        result = get_landlord_id_via_kafka(access_token)

        # Assertions to verify behavior
        assert result == "test-landlord-id"
        mock_send.assert_called_once_with('user-validation-request', {
            "action": "validate_token",
            "access_token": access_token
        })

# Test for Kafka producer error when sending a message
@patch("app.routes.landlords_routes.producer.send")
def test_get_landlord_id_via_kafka_send_error(mock_send):
    # Simulate an exception being raised when sending the message
    mock_send.side_effect = Exception("Kafka send error")

    access_token = "mock_access_token"

    with pytest.raises(HTTPException) as exc_info:
        get_landlord_id_via_kafka(access_token)

    assert exc_info.value.status_code == 404
    assert str(exc_info.value.detail) == "Landlord not found or unauthorized"
    mock_send.assert_called_once_with('user-validation-request', {
        "action": "validate_token",
        "access_token": access_token
    })

# Test function for expense creation with file upload
@patch("app.routes.landlords_routes.get_tenant_data")
@patch("app.routes.landlords_routes.producer.send")
@patch("app.routes.landlords_routes.s3_client")
def test_create_expense_with_file_upload(mock_s3_client, mock_producer_send, mock_get_tenant_data, client, db_session):
    # Mock S3 upload response
    mock_s3_client.upload_fileobj = MagicMock()

    # Mock tenant data response
    mock_get_tenant_data.return_value = [{"email": "tenant1@example.com", "name": "Tenant One"}]

    # Create tenants in the database
    tenant1 = Tenents(id=1, house_id=create_expense["house_id"], tenent_id="1")
    tenant2 = Tenents(id=2, house_id=create_expense["house_id"], tenent_id="2")
    db_session.add_all([tenant1, tenant2])
    db_session.commit()

    # Prepare file and expense data
    files = generate_mock_file()
    expense_data_json = json.dumps(create_expense)

    # Send POST request
    response = client.post(
        "/houses/addExpense",
        data={"expense_data": expense_data_json},
        files=files,
    )

    # Assertions to check the response and behavior
    assert response.status_code == 200
    response_json = response.json()
    assert "id" in response_json
    assert response_json["title"] == create_expense["title"]
    assert response_json["amount"] == create_expense["amount"]
    assert response_json["file_path"] is not None

    # Verify the division of the expense among tenants
    tenant_expenses = db_session.query(TenantExpense).filter(
        TenantExpense.expense_id == response_json["id"]
    ).all()
    assert len(tenant_expenses) == 2  # Two tenants

    # Retrieve the expected shared amount
    shared_amount = round(create_expense["amount"] / len(tenant_expenses), 2)
    
    for tenant_expense in tenant_expenses:
        assert tenant_expense.amount == shared_amount

    # Verify that Kafka producer was called
    mock_producer_send.assert_called_once()
    kafka_message = mock_producer_send.call_args[0][1]

    # Assertions for Kafka message
    assert kafka_message["action"] == "expense_created"
    assert kafka_message["user_data"]["expense_details"]["title"] == create_expense["title"]
    assert kafka_message["user_data"]["expense_details"]["deadline_date"] == create_expense["deadline_date"]

    # Assertions for tenant data in Kafka message
    users = kafka_message["user_data"]["users"]
    assert len(users) == 2
    assert users[0]["email"] == "tenant1@example.com"
    assert users[0]["name"] == "Tenant One"

@patch("sqlalchemy.orm.Session.query")
def test_create_tenant_expenses_invalid_amount(mock_query, db_session):
    """Test case when expense amount is invalid (None or not numeric)."""
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = None  # Valor inválido

    with pytest.raises(HTTPException) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Expense amount cannot be null or non-numeric"

@patch("sqlalchemy.orm.Session.bulk_save_objects", side_effect=Exception("Database error"))
def test_create_tenant_expenses_bulk_save_failure(mock_bulk_save, db_session):
    """Test case when bulk_save_objects raises an exception."""
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]

    db_session.query.return_value.filter.return_value.all.return_value = tenants_mock

    with pytest.raises(Exception) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert str(excinfo.value) == "Database error"
    mock_bulk_save.assert_called_once()

@patch("sqlalchemy.orm.Session.query")
def test_create_tenant_expenses_no_tenants(mock_query, db_session):
    """Test case when there are no tenants in the house."""
    # Mock da consulta para retornar uma despesa mockada
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0
    expense_mock.title = "Test Expense"
    expense_mock.description = "Shared expense"
    expense_mock.created_at = datetime.now().date()
    expense_mock.deadline_date = datetime.now().date()
    expense_mock.status = "pending"

    # Configurar o mock para retornar a despesa simulada
    mock_query.return_value.filter.return_value.first.return_value = expense_mock

    # Verificar o comportamento ao não encontrar inquilinos
    with pytest.raises(HTTPException) as excinfo:
        create_tenant_expenses(expense_mock, db_session)
    
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "No tenants available for expense division"

@patch("sqlalchemy.orm.Session.query")
def test_create_tenant_expenses_no_tenants_in_db(mock_query, db_session):
    """Test case when the query for tenants returns an empty list."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    # Simular lista vazia para tenants
    mock_query.return_value.filter.return_value.all.return_value = []

    # Verificar que a exceção é levantada
    with pytest.raises(HTTPException) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "No tenants found for the given house"

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_single_tenant(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case when there is only one tenant."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    # Mock do único tenant
    tenant_mock = [MagicMock(id=1, house_id=1, tenent_id="1")]

    # Configurar mocks
    mock_query.return_value.filter.return_value.all.return_value = tenant_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar chamadas de salvar e commit
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]
    assert len(tenant_expenses) == 1  # Apenas um tenant
    assert isclose(tenant_expenses[0].amount, 1000.0, rel_tol=1e-9)
    mock_commit.assert_called_once()

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_zero_amount(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case when the expense amount is zero."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 0.0

    # Mock dos tenants
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]

    # Configurar mocks
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar chamadas de salvar
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]
    assert len(tenant_expenses) == 2  # Dois tenants
    for tenant_expense in tenant_expenses:
        assert isclose(tenant_expense.amount, 0.0, abs_tol=1e-9)

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_small_amount(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case when the expense amount is very small."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 0.01

    # Mock dos tenants
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]

    # Configurar mocks
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar chamadas de salvar
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]
    assert len(tenant_expenses) == 2  # Dois tenants

    # Verificar que o último tenant recebeu todo o montante
    assert isclose(tenant_expenses[0].amount, 0.0, abs_tol=1e-9)
    assert isclose(tenant_expenses[1].amount, 0.01, abs_tol=1e-9)


@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit", side_effect=Exception("Commit failed"))
def test_create_tenant_expenses_commit_failure(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case when commit fails."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    # Mock dos tenants
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]

    # Configurar mocks
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Verificar que uma exceção é levantada
    with pytest.raises(Exception) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert str(excinfo.value) == "Commit failed"
    mock_bulk_save.assert_called_once()
    mock_commit.assert_called_once()



@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_with_uneven_division(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case when the expense amount cannot be evenly divided among tenants."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0
    expense_mock.title = "Test Expense"
    expense_mock.description = "Shared expense"
    expense_mock.created_at = datetime.now()
    expense_mock.deadline_date = datetime.now()
    expense_mock.status = "pending"

    # Mock dos inquilinos
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
        MagicMock(id=3, house_id=1, tenent_id="3"),
    ]

    # Configurar mocks
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar que a função de salvar múltiplos objetos foi chamada
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]

    # Verificar que todas as despesas foram criadas corretamente
    assert len(tenant_expenses) == 3

    # Validar que a soma é consistente com arredondamento para uma casa decimal
    total_amount = round(sum(te.amount for te in tenant_expenses), 1)
    assert total_amount == round(expense_mock.amount, 1)

    # Verificar arredondamento esperado para cada parcela
    share_per_tenant = round(expense_mock.amount / len(tenants_mock), 1)
    total_allocated = round(share_per_tenant * (len(tenants_mock) - 1), 1)
    expected_last_share = round(expense_mock.amount - total_allocated, 1)

    for i, tenant_expense in enumerate(tenant_expenses):
        if i < len(tenants_mock) - 1:
            assert tenant_expense.amount == share_per_tenant
        else:
            assert tenant_expense.amount == expected_last_share


@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_bulk_save_called(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case to ensure bulk_save_objects is called for tenant expenses."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1500.0
    expense_mock.title = "Test Expense"
    expense_mock.description = "Shared expense"
    expense_mock.created_at = datetime.now()
    expense_mock.deadline_date = datetime.now()
    expense_mock.status = "pending"

    # Mock dos inquilinos
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]

    # Configurar mocks
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar que a função de salvar múltiplos objetos foi chamada
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]

    # Verificar que as despesas foram corretamente criadas
    assert len(tenant_expenses) == 2  # Dois inquilinos
    for tenant_expense in tenant_expenses:
        assert tenant_expense.amount == round(expense_mock.amount / 2, 2)

    # Verificar que a função commit foi chamada
    mock_commit.assert_called_once()

@patch("sqlalchemy.orm.Session.query")
def test_create_tenant_expenses_negative_amount(mock_query, db_session):
    """Test case when the expense amount is negative."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = -100.0

    # Mock dos tenants
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Verificar que a exceção é levantada
    with pytest.raises(HTTPException) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "Expense amount cannot be negative"

@patch("sqlalchemy.orm.Session.query")
def test_create_tenant_expenses_zero_amount_no_tenants(mock_query, db_session):
    """Test case when the expense amount is zero and no tenants exist."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 0.0

    # Simular lista vazia para tenants
    mock_query.return_value.filter.return_value.all.return_value = []

    # Verificar que uma exceção é levantada
    with pytest.raises(HTTPException) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert excinfo.value.status_code == 404
    assert excinfo.value.detail == "No tenants found for the given house"

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_large_amount(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case with a very large expense amount."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1e9  # Um bilhão

    # Mock dos tenants
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar chamadas de salvar
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]
    assert len(tenant_expenses) == 2
    assert sum(te.amount for te in tenant_expenses) == pytest.approx(1e9, abs=0.1)

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
@patch("sqlalchemy.orm.Session.commit")
def test_create_tenant_expenses_duplicate_tenants(mock_commit, mock_bulk_save, mock_query, db_session):
    """Test case when duplicate tenants are returned."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    # Mock dos tenants duplicados
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=1, house_id=1, tenent_id="1"),  # Duplicado
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar chamadas de salvar
    mock_bulk_save.assert_called_once()
    tenant_expenses = mock_bulk_save.call_args[0][0]
    assert len(tenant_expenses) == 2  # Deve ignorar duplicatas
    assert isclose(sum(te.amount for te in tenant_expenses), 1000.0, abs_tol=1e-9)

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects", side_effect=Exception("Bulk save failed"))
def test_create_tenant_expenses_bulk_save_failure(mock_bulk_save, mock_query, db_session):
    """Test case when bulk_save_objects raises an exception."""
    # Mock da despesa
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    # Mock dos tenants
    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Verificar que uma exceção é levantada
    with pytest.raises(Exception) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert str(excinfo.value) == "Bulk save failed"
    mock_bulk_save.assert_called_once()

@patch("sqlalchemy.orm.Session.query")
def test_create_tenant_expenses_invalid_house_id(mock_query, db_session):
    """Test case when expense house_id is invalid or None."""
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = None  # house_id inválido
    expense_mock.amount = 1000.0

    with pytest.raises(HTTPException) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert excinfo.value.status_code == 400
    assert excinfo.value.detail == "House ID cannot be null or invalid"

@patch("sqlalchemy.orm.Session.query", side_effect=Exception("Database query failed"))
def test_create_tenant_expenses_query_failure(mock_query, db_session):
    """Test case when the query for tenants fails."""
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    with pytest.raises(Exception) as excinfo:
        create_tenant_expenses(expense_mock, db_session)

    assert str(excinfo.value) == "Database query failed"

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
def test_create_tenant_expenses_amount_mismatch(mock_bulk_save, mock_query, db_session):
    """Test case to ensure total distributed amount matches expense amount."""
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Chamar a função
    create_tenant_expenses(expense_mock, db_session)

    # Verificar o valor total distribuído
    tenant_expenses = mock_bulk_save.call_args[0][0]
    total_distributed = sum(te.amount for te in tenant_expenses)
    assert total_distributed == pytest.approx(expense_mock.amount, abs=0.1)

@patch("sqlalchemy.orm.Session.query")
@patch("sqlalchemy.orm.Session.bulk_save_objects")
def test_create_tenant_expenses_initialization_failure(mock_bulk_save, mock_query, db_session):
    """Test case when TenantExpense initialization fails."""
    expense_mock = MagicMock()
    expense_mock.id = 1
    expense_mock.house_id = 1
    expense_mock.amount = 1000.0

    tenants_mock = [
        MagicMock(id=1, house_id=1, tenent_id="1"),
        MagicMock(id=2, house_id=1, tenent_id="2"),
    ]
    mock_query.return_value.filter.return_value.all.return_value = tenants_mock

    # Forçar erro durante a criação de TenantExpense
    with patch("app.routes.landlords_routes.TenantExpense", side_effect=Exception("Initialization error")):
        with pytest.raises(Exception) as excinfo:
            create_tenant_expenses(expense_mock, db_session)

        assert str(excinfo.value) == "Initialization error"

# Test function for handling invalid JSON in expense_data
def test_create_expense_with_invalid_json(client):

    # Create a mock file upload
    files = generate_mock_file()
    invalid_expense_data = "{invalid_json: true"  # Intentionally malformed JSON

    response = client.post(
        "/houses/addExpense",
        data={"expense_data": invalid_expense_data},
        files=files
    )

    # Assertions to check the response and behavior for invalid JSON
    assert response.status_code == 400
    response_json = response.json()
    assert response_json["detail"] == "Invalid JSON format"

# Test function for handling NoCredentialsError during file upload
@patch("app.routes.landlords_routes.s3_client")
def test_create_expense_with_no_credentials_error(mock_s3_client, client):
    # Simulate NoCredentialsError
    mock_s3_client.upload_fileobj.side_effect = NoCredentialsError

    # Create a mock file upload
    files = generate_mock_file()
    expense_data_json = json.dumps(create_expense)

    response = client.post(
        "/houses/addExpense",
        data={"expense_data": expense_data_json},
        files=files
    )

    # Print response for debugging
    print("Response content:", response.text)

    # Assertions to check the response and behavior for NoCredentialsError
    assert response.status_code == 400  # Ensure the status code matches the route
    response_json = response.json()
    assert "error" in response_json, "Expected 'error' key not found in response"
    assert response_json["error"] == "Credenciais não encontradas"



# Test function for handling generic exceptions during file upload
@patch("app.routes.landlords_routes.s3_client")
def test_create_expense_with_generic_exception(mock_s3_client, client):
    # Simulate a generic exception
    mock_s3_client.upload_fileobj.side_effect = Exception("Unexpected error")

    # Create a mock file upload
    files = generate_mock_file()
    expense_data_json = json.dumps(create_expense)

    response = client.post(
        "/houses/addExpense",
        data={"expense_data": expense_data_json},
        files=files
    )

    # Assertions to check the response and behavior for a generic exception
    assert response.status_code == 400
    response_json = response.json()
    assert "error" in response_json, "Expected 'error' key not found in response"
    assert response_json["error"] == "Unexpected error"

# Test function for retriving all expenses from a house
def test_get_expenses_by_house(client):
    expenses_list = [
        {
            "id": 1,
            "house_id": 1,
            "amount": 1000.0,
            "title": "Rent",
            "description": "Monthly rent",
            "created_at": "2024-12-01T00:00:00",
            "deadline_date": "2024-12-01T00:00:00",
            "file_path": None,
            "status": "pending",  # Add this line
            "tenants": [{"tenant_id": 1, "status": "paid"}]  # Correct the field name
        }
    ]

    with patch("sqlalchemy.orm.Query.all", return_value=expenses_list):
        response = client.get("/houses/expenses/1")
        assert response.status_code == 200
        response_json = response.json()
        assert len(response_json) == 1
        assert response_json[0]["title"] == "Rent"
        assert response_json[0]["amount"] == 1000


# Test function for retriving all expenses from a house when there is no expenses
def test_get_expenses_by_house_when_there_is_no_expenses(client):
    response = client.get("/houses/expenses/1")
    assert response.status_code == 404
    response_json = response.json()
    assert response_json["detail"] == "Expenses not found for house 1"

# Test function for creating a tenant and associating it with a house
@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_create_tenant(mocked_kafka_cognito_id, client):
    mocked_kafka_cognito_id.return_value = "test-landlord-id"

    tenant_data = {
        "house_id": 1,
        "rent": 1000,
        "name": "John Doe",
        "email": "johndoe@example.com"
    }

    response_data = {
        "house_id": 1,
        "rent": 1000,
        "tenant_id": "test-tenant-id",
        "name": "John Doe",
        "email": "johndoe@example.com",
        "contract": "Test Contract"  # Add a valid string
    }

    with patch("app.routes.landlords_routes.create_user_in_user_microservice", return_value="test-tenant-id"):
        response = client.post(
            "/houses/tenents",
            json=tenant_data
        )

        assert response.status_code == 200
        response_json = response.json()
        assert response_json["house_id"] == 1
        assert response_json["rent"] == 1000
        assert response_json.get("tenent_id") == "test-tenant-id"

# # Test fucntion for getting all tenants associated with a house
# @patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
# def test_get_tenants_by_house(mocked_kafka_cognito_id, client):
#     mocked_kafka_cognito_id.return_value = "test-landlord-id"
#     access_token = "mock_access_token"


#     house = {
#         "id": 1,
#         "address": "123 Test St",
#         "name": "House 1",
#         "state": "TS",
#         "landlord_id": "test-landlord-id",
#         "city": "Test City",
#         "zipcode": "12345"
#     }
    

#     tenants_list = [
#         Tenents(tenent_id="test-tenant-id", rent=1000, house_id=1)
#     ]
    
#     with patch("app.models.models.House.query.first", return_value=house):
#         with patch("app.models.models.Tenents.query.all", return_value=tenants_list):
#             client.cookies.set("access_token", access_token)
#             response = client.get("/houses/landlord/house/1")
#             assert response.status_code == 200
#             response_json = response.json()
#             assert "house" in response_json
#             assert "tenents" in response_json
#             assert response_json["tenents"][0].get("rent") == 1000
#             assert response_json["tenents"][0].get("tenant_id") == "test-tenant-id"

#     mocked_kafka_cognito_id.assert_called_once_with(access_token)



# Test fucntion for getting all tenants associated with a house when there is no access_token
def test_get_tenants_by_house_with_no_access_token(client):
    
    response = client.get("houses/landlord/house/1")
    assert response.status_code == 401
    response_json = response.json()
    assert response_json["detail"] == "Access token missing"

# Test fucntion for getting all tenants associated with a house when the landlord is not found
@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_get_tenants_by_house_with_no_landlord(mocked_kafka_cognito_id, client):
    mocked_kafka_cognito_id.return_value = None
    access_token = "mock_access_token"

    client.cookies.set("access_token", access_token)
    response = client.get("houses/landlord/house/1")
    assert response.status_code == 404
    response_json = response.json()
    assert response_json["detail"] == "Landlord not found or unauthorized"
    mocked_kafka_cognito_id.assert_called_once_with(access_token)

# Test fucntion for getting all tenants associated with a house when the house is not found
@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_get_tenants_by_house_with_no_house_found(mocked_kafka_cognito_id, client):
    mocked_kafka_cognito_id.return_value = "test-landlord-id"
    access_token = "mock_access_token"

    with patch("sqlalchemy.orm.Query.first", return_value=None):
        client.cookies.set("access_token", access_token)
        response = client.get("houses/landlord/house/1")
        assert response.status_code == 404
        response_json = response.json()
        assert response_json["detail"] == "House not found"
    
# @patch("app.routes.landlords_routes.producer.send")
# @patch("app.routes.landlords_routes.user_cache", new_callable=dict)
# def test_create_user_in_user_microservice_success(mock_user_cache, mock_producer_send):
#     user_data = {
#         "name": "John Doe",
#         "email": "johndoe@example.com"
#     }

#     # Mock the Kafka producer's `send` method
#     mock_producer_send.return_value = MagicMock()
#     mock_producer_send.return_value.get.return_value = None  # Simulate successful send

#     # Set the user_cache to simulate finding a cognito_id
#     mock_user_cache["cognito_id"] = "test-cognito-id"

#     # Call the function
#     result = create_user_in_user_microservice(user_data)

#     # Assertions
#     assert result == "test-cognito-id"
#     mock_producer_send.assert_called_once_with('user-creation-request', {
#         "action": "create_user",
#         "user_data": user_data
#     })

# Test function for handling send error
@patch("app.routes.landlords_routes.producer.send")
def test_create_user_in_user_microservice_send_error(mock_producer_send):
    user_data = {
        "name": "John Doe",
        "email": "johndoe@example.com"
    }

    # Simulate an exception being raised when sending the message
    mock_producer_send.side_effect = Exception("Kafka send error")

    with pytest.raises(HTTPException) as exc_info:
        create_user_in_user_microservice(user_data)

    # Assertions
    assert exc_info.value.status_code == 404
    assert str(exc_info.value.detail) == "User not found or unauthorized"
    mock_producer_send.assert_called_once_with('user-creation-request', {
        "action": "create_user",
        "user_data": user_data
    })

# Test function for handling timeout while waiting for user ID
@patch("app.routes.landlords_routes.producer.send")
@patch("app.routes.landlords_routes.user_cache", {})
def test_create_user_in_user_microservice_timeout(mock_producer_send):
    user_data = {
        "name": "John Doe",
        "email": "johndoe@example.com"
    }

    # Mock the Kafka producer's `send` method
    # Mock do método `send`
    mock_future = MagicMock()
    mock_producer_send.return_value = mock_future
    mock_producer_send.return_value.get.return_value = None  # Simulate successful send

    with pytest.raises(HTTPException) as exc_info:
        create_user_in_user_microservice(user_data)

    # Assertions
    assert exc_info.value.status_code == 404
    assert str(exc_info.value.detail) == "User not found or unauthorized"

    # Verificar chamadas relevantes
    from unittest.mock import call
    expected_calls = [
        call('user-creation-request', {"action": "create_user", "user_data": user_data}),
        call('invite-request', {"action": "create_user", "user_data": user_data}),
    ]

    # Filtrar chamadas relevantes (removendo call().get(timeout=10))
    relevant_calls = [call for call in mock_producer_send.mock_calls if 'get' not in str(call)]

    # Validar apenas as chamadas relevantes
    assert relevant_calls == expected_calls


# # Test function for marking tenant payment
# @patch("sqlalchemy.orm.Session.commit")
# def test_mark_tenant_payment(mock_commit, client):
#     # Create a mock tenant expense record
#     tenant_expense = TenantExpense(tenant_id=1, expense_id=1, status='pending')

#     # Create a mock session
#     mock_db = MagicMock()
#     mock_db.query.return_value.filter.return_value.first.return_value = tenant_expense

#     # Patch the `get_db` dependency to return the mock session
#     with patch("app.routes.landlords_routes.get_db", return_value=mock_db):
#         # Send a PUT request to mark tenant payment
#         response = client.put("/tenants/1/pay?expense_id=1")

#         # Assertions
#         assert response.status_code == 200
#         response_data = response.json()
#         assert response_data["message"] == "Tenant payment updated successfully"
#         mock_commit.assert_called_once()

def test_mark_tenant_payment_not_found(client):
    # Mock the database query to return None
    with patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None
        
        # Send a PUT request to mark tenant payment
        response = client.put("/tenants/1/pay?expense_id=1")

        # Assertions
        assert response.status_code == 404
        assert response.json()["detail"] == "Not Found"  # Ensure this matches the route's detail

# Test for getting a specific expense by ID
@patch("sqlalchemy.orm.Session.query")
def test_get_expense_by_id(mock_query, client):
    # Create a mock expense record with date fields
    expense = Expense(
        id=1,
        house_id=1,
        amount=1000.0,
        title="Rent",
        description="Monthly rent",
        created_at=datetime.now().date(),  # Convert to date
        deadline_date=datetime.now().date(),  # Convert to date
        file_path=None,
        status="pending"
    )
    mock_query.return_value.filter.return_value.first.return_value = expense

    response = client.get("/houses/expense/1")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == expense.id
    assert response_data["title"] == expense.title

def test_get_expense_by_id_not_found(client):
    with patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        response = client.get("/houses/expense/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense not found"

# Test for deleting an expense
@patch("sqlalchemy.orm.Session.commit")
def test_delete_expense(mock_commit, client):
    expense = Expense(id=1, house_id=1, amount=1000.0, title="Rent")

    # Mock the session and ensure the delete method does not throw errors
    with patch("sqlalchemy.orm.Session.query") as mock_query, patch("sqlalchemy.orm.Session.delete") as mock_delete:
        mock_query.return_value.filter.return_value.first.return_value = expense
        
        # Ensure the delete method is mocked to accept the instance without issues
        mock_delete.return_value = None

        response = client.delete("/houses/expenses/1")

        # Assertions
        assert response.status_code == 200
        assert response.json()["message"] == "Expense deleted successfully"
        mock_commit.assert_called_once()
        mock_delete.assert_called_once_with(expense)

def test_delete_expense_not_found(client):
    with patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        response = client.delete("/houses/expenses/999")

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense not found"

# # Test for marking an expense as paid
# @patch("sqlalchemy.orm.Session.commit")
# @patch("sqlalchemy.orm.Session.refresh")
# def test_mark_expense_as_paid(mock_refresh, mock_commit, client):
#     # Create an expense instance and tenant expense instances
#     expense = Expense(id=1, house_id=1, amount=1000.0, title="Rent", status="pending")
#     tenant_expenses = [
#         TenantExpense(tenant_id=1, expense_id=1, status="paid"),
#         TenantExpense(tenant_id=2, expense_id=1, status="paid")
#     ]

#     # Create a mock session and configure return values for query
#     mock_session = MagicMock()
#     mock_session.query.return_value.filter.return_value.first.return_value = expense
#     mock_session.query.return_value.filter.return_value.all.return_value = tenant_expenses

#     # Patch `get_db` to use the mock session
#     with patch("app.routes.landlords_routes.get_db", return_value=mock_session):
#         response = client.put("/houses/expenses/1/mark-paid")

#         # Assertions
#         assert response.status_code == 200
#         response_data = response.json()
#         assert response_data["message"] == "Expense status updated"
#         assert response_data["status"] == "paid"
#         mock_commit.assert_called_once()
#         mock_refresh.assert_called_once_with(expense)

def test_mark_expense_as_paid_not_found(client):
    with patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = None

        response = client.put("/houses/expenses/999/mark-paid")

        assert response.status_code == 404
        assert response.json()["detail"] == "Expense not found"

@patch("app.routes.landlords_routes.get_tenant_data")
@patch("app.routes.landlords_routes.producer.send")
@patch("app.routes.landlords_routes.s3_client")
def test_uploadContract_succeed(mock_s3_client, mock_producer_send, mock_get_tenant_data, db_session, client):
    # Mock do S3
    mock_s3_client.upload_fileobj = MagicMock()

    # Criar tenant na sessão de teste
    tenant = Tenents(id=1, house_id=1, tenent_id="1", contract=None)
    db_session.add(tenant)
    db_session.commit()

    # Mock de get_tenant_data
    mock_get_tenant_data.return_value = [{"email": "test@example.com", "name": "John Doe"}]

    # Mock do producer.send
    mock_producer_send.return_value = MagicMock()

    # Dados para a requisição
    files = {"file": ("test_file.pdf", b"Mock file content", "application/pdf")}
    contract_data = {"tenant_id": "1"}

    response = client.post(
        "/houses/uploadContract",
        data={"contract_data": json.dumps(contract_data)},
        files=files,
    )

    # Verificações
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["message"] == "Contract uploaded successfully"
    assert response_json["file_url"] is not None

    # Verificar chamadas
    mock_get_tenant_data.assert_called_once_with(["1"])
    mock_producer_send.assert_called_once_with(
        "invite-request",
        {
            "action": "upload_contract",
            "user_data": {
                "email": "test@example.com",
                "name": "John Doe"
            }
        }
    )

# def test_uploadContract_tenant_not_found(client):
#     # Mock the database query to return None for the tenant
#     with patch("sqlalchemy.orm.Session.query") as mock_query:
#         mock_query.return_value.filter.return_value.first.return_value = None

#         # Create a mock file upload
#         files = {
#             "file": ("test_file.pdf", b"Mock file content", "application/pdf"),
#         }
#         contract_data = {"tenant_id": 1}

#         response = client.post(
#             "/houses/uploadContract",
#             data={"contract_data": json.dumps(contract_data)},
#             files=files,
#         )

#         # Assertions to check the response and behavior
#         assert response.status_code == 404
#         response_json = response.json()
#         assert response_json["detail"] == "Tenant not found"

def test_uploadContract_invalid_json(client):
    # Create a mock file upload
    files = {
        "file": ("test_file.pdf", b"Mock file content", "application/pdf"),
    }

    # Invalid JSON for contract_data
    invalid_contract_data = "{tenant_id: 1"  # Missing closing brace and incorrect formatting

    response = client.post(
        "/houses/uploadContract",
        data={"contract_data": invalid_contract_data},  # Pass the invalid JSON
        files=files,
    )

    # Assertions to check the response and behavior
    assert response.status_code == 400
    response_json = response.json()
    assert response_json["detail"] == "Invalid JSON format"


@patch("app.routes.landlords_routes.get_tenant_data")
@patch("app.routes.landlords_routes.s3_client")
def test_uploadContract_filename_with_spaces(mock_s3_client, mock_get_tenant_data, db_session, client):
    # Mock do S3 para aceitar upload sem erros
    mock_s3_client.upload_fileobj = MagicMock()

    # Configurar mock para get_tenant_data
    mock_get_tenant_data.return_value = [{"email": "test@example.com", "name": "John Doe"}]

    # Criar tenant no banco de dados
    tenant = Tenents(id=1, house_id=1, tenent_id="1", contract=None)
    db_session.add(tenant)
    db_session.commit()

    # Dados do arquivo
    files = {
        "file": ("test file with spaces.pdf", b"Mock file content", "application/pdf"),
    }
    contract_data = {"tenant_id": "1"}

    # Enviar requisição POST
    response = client.post(
        "/houses/uploadContract",
        data={"contract_data": json.dumps(contract_data)},
        files=files,
    )

    # Verificações
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["message"] == "Contract uploaded successfully"
    assert "test_file_with_spaces.pdf" in response_json["file_url"]

    # Verificar chamadas
    mock_get_tenant_data.assert_called_once_with(["1"])
    mock_s3_client.upload_fileobj.assert_called_once()

def test_uploadContract_no_credentials_error(client):
    # Mock the S3 upload to raise NoCredentialsError
    with patch("app.routes.landlords_routes.s3_client.upload_fileobj") as mock_upload:
        mock_upload.side_effect = NoCredentialsError

        # Create a mock file upload
        files = {
            "file": ("test_file.pdf", b"Mock file content", "application/pdf"),
        }
        contract_data = {"tenant_id": "1"}

        response = client.post(
            "/houses/uploadContract",
            data={"contract_data": json.dumps(contract_data)},
            files=files,
        )

        # Assertions to verify the response
        assert response.status_code == 400
        response_json = response.json()
        assert response_json["error"] == "Credenciais não encontradas"

def test_uploadContract_generic_exception(client):
    # Mock the S3 upload to raise a generic exception
    with patch("app.routes.landlords_routes.s3_client.upload_fileobj") as mock_upload:
        mock_upload.side_effect = Exception("Generic error occurred")

        # Create a mock file upload
        files = {
            "file": ("test_file.pdf", b"Mock file content", "application/pdf"),
        }
        contract_data = {"tenant_id": "1"}

        response = client.post(
            "/houses/uploadContract",
            data={"contract_data": json.dumps(contract_data)},
            files=files,
        )

        # Assertions to verify the response
        assert response.status_code == 400
        response_json = response.json()
        assert response_json["error"] == "Generic error occurred"