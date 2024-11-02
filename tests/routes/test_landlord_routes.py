import pytest
from app.models import Expense, House
from unittest.mock import patch, MagicMock
import json
from botocore.exceptions import NoCredentialsError
from datetime import datetime

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
    assert response_json["amount"] == 1000.0
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
        assert response_json[0]["amount"] == 1000.0


# Test function for retriving all expenses from a house when there is no expenses
def test_get_expenses_by_house_when_there_is_no_expenses(client):

    response = client.get("/houses/expenses/1")
    assert response.status_code == 404
    response_json = response.json()
    assert response_json["detail"] == "Expenses not found for house 1"
