import pytest
from app.models import House
from unittest.mock import patch, MagicMock
from app.routes.landlords_routes import get_landlord_id_via_kafka
from fastapi import HTTPException

# Define the data to be sent in the POST request
house_data = {
    "name": "Test House",
    "landlord_id": "test-landlord-id",
    "address": "123 Test St",
    "city": "Test City",
    "state": "TS",
    "zipcode": "12345"
}

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
