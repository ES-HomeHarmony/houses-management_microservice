import pytest
from fastapi import HTTPException
from app.models import Expense, House
from app.routes.landlords_routes import get_landlord_id_via_kafka
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


# Mock test for getting houses by landlord endpoint
@patch("app.routes.landlords_routes.get_landlord_id_via_kafka")
def test_get_houses_by_landlord(mock_get_landlord, client):
    # Sample data for house retrieval
    house_list = [
        {
            "name": "House 1",
            "landlord_id": "test-landlord-id",
            "address": "123 Test St",
            "city": "Test City",
            "state": "TS",
            "zipcode": "12345"
        },
        {
            "name": "House 2",
            "landlord_id": "test-landlord-id",
            "address": "456 Another St",
            "city": "Test City",
            "state": "TS",
            "zipcode": "67890"
        }
    ]

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
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 2
        assert response_data[0]["name"] == house_list[0]["name"]
        assert response_data[1]["name"] == house_list[1]["name"]

        # Verify that the get_landlord_id_via_kafka function was called with the correct access token
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
            "file_path": None
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