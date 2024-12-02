import pytest
from fastapi import HTTPException
from app.models import Expense, House, Tenents
from app.routes.landlords_routes import get_landlord_id_via_kafka, create_user_in_user_microservice
from unittest.mock import patch, MagicMock
from botocore.exceptions import NoCredentialsError
from datetime import datetime
import json


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
def test_create_expense_with_file_upload(mock_s3_client, client):
    # Mock the S3 upload response
    mock_s3_client.upload_fileobj.return_value = "https://test-bucket.s3.us-east-1.amazonaws.com/expenses/test_file.pdf"

    # Create a mock file upload
    files = generate_mock_file()
    expense_data_json = json.dumps(create_expense)

    # Mock the database query to return tenants for the given house
    with patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.all.return_value = [
            Tenents(id=1, house_id=create_expense["house_id"]),
            Tenents(id=2, house_id=create_expense["house_id"])
        ]

        response = client.post(
            "/houses/addExpense",
            data={"expense_data": expense_data_json},
            files=files
        )

        # Assertions to check the response and behavior
        assert response.status_code == 200
        response_json = response.json()
        assert "id" in response_json
        assert response_json["title"] == "Rent"
        assert response_json["amount"] == 1000
        assert response_json["file_path"] is not None


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
    mock_producer_send.return_value = MagicMock()
    mock_producer_send.return_value.get.return_value = None  # Simulate successful send

    with pytest.raises(HTTPException) as exc_info:
        create_user_in_user_microservice(user_data)

    # Assertions
    assert exc_info.value.status_code == 404
    assert str(exc_info.value.detail) == "User not found or unauthorized"
    mock_producer_send.assert_called_once_with('user-creation-request', {
        "action": "create_user",
        "user_data": user_data
    })



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

def test_uploadContract_succeed(client, mock_s3_client):
    # Mock the S3 upload response
    mock_s3_client.upload_fileobj = MagicMock()

    # Mock the tenant instance
    tenant = MagicMock(spec=Tenents)
    tenant.id = 1
    tenant.house_id = 1
    tenant.contract = None

    # Mock the database session to return the tenant instance
    with patch("sqlalchemy.orm.Session.query") as mock_query, patch("sqlalchemy.orm.Session.commit"), patch("sqlalchemy.orm.Session.refresh") as mock_refresh:
        mock_query.return_value.filter.return_value.first.return_value = tenant

        # Mock the refresh method to simulate the object being persistent
        mock_refresh.side_effect = lambda obj: setattr(obj, "contract", "mock_updated_contract_url")

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

        # Assertions to check the response and behavior
        assert response.status_code == 200
        response_json = response.json()
        assert response_json["message"] == "Contract uploaded successfully"
        assert response_json["file_url"] is not None

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


def test_uploadContract_filename_with_spaces(client, mock_s3_client):
    # Mock the S3 upload response
    mock_s3_client.upload_fileobj = lambda file, bucket, key: None

    # Create a real `Tenents` instance
    tenant = Tenents(id=1, house_id=1)
    tenant.contract = None

    # Mock the database query to return the real tenant instance
    with patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = tenant

        # Mock the commit and refresh methods
        with patch("sqlalchemy.orm.Session.commit"), patch("sqlalchemy.orm.Session.refresh"):
            # File with spaces in the name
            files = {
                "file": ("test file with spaces.pdf", b"Mock file content", "application/pdf"),
            }
            contract_data = {"tenant_id": "1"}

            response = client.post(
                "/houses/uploadContract",
                data={"contract_data": json.dumps(contract_data)},
                files=files,
            )

            # Assertions
            assert response.status_code == 200
            response_json = response.json()
            assert response_json["message"] == "Contract uploaded successfully"
            # Verify that the filename was modified to replace spaces with underscores
            assert "test_file_with_spaces.pdf" in response_json["file_url"]

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