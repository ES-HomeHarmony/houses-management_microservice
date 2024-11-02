from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from kafka import KafkaConsumer, KafkaProducer
import json
import threading
import os
from app.database import get_db
from app.models import House
from app.schemas import HouseCreate, HouseResponse
from typing import List
import time


router = APIRouter(
    prefix="/houses",
    tags=["houses"],
)

producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Kafka consumer for receiving responses
consumer = KafkaConsumer(
    'user-validation-response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='houses_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("Kafka consumer initialized and listening...")
print(f"Subscribed topics: {consumer.subscription()}")
print(f"KAFKA_BOOTSTRAP_SERVERS: {os.getenv('KAFKA_BOOTSTRAP_SERVERS')}")

user_cache = {}

# Run the consumer in a separate thread to listen for responses
def start_consumer():
    for message in consumer:
        print(f"Received message: {message.value.get('cognito_id')}")
        print(f"Received message: {message.value}")
        user_cache["cognito_id"] = message.value.get("cognito_id")

threading.Thread(target=start_consumer, daemon=True).start()

def get_landlord_id_via_kafka(access_token: str):
    # Send a message to Kafka for user validation
    validation_request = {
        "action": "validate_token",
        "access_token": access_token
    }
    
    try:
        future = producer.send('user-validation-request', validation_request)
        result = future.get(timeout=10)  # Block until the send is acknowledged or times out
        print(f"Message sent successfully: {result}")
    except Exception as e:
        print(f"Error sending message to Kafka: {e}")

    # Wait for validation response
    cognito_id_landlord = None
    for _ in range(10):  # Retry mechanism with limited attempts
        print(f"Checking for cognito_id in cache: {user_cache}")
        
        if "cognito_id" in user_cache.keys():
            cognito_id_landlord = user_cache.get("cognito_id")
            print(f"Found cognito_id {cognito_id_landlord}")
            break
        time.sleep(1)  # Add a sleep to avoid busy-waiting

    if not cognito_id_landlord:
        raise HTTPException(status_code=404, detail="Landlord not found or unauthorized")

    return cognito_id_landlord

@router.post("/create", response_model=HouseResponse)
async def create_house(house: HouseCreate, db: Session = Depends(get_db), request: Request = None):
    
    # Extract access_token from cookies
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")

    cognito_id_landlord = get_landlord_id_via_kafka(access_token)

    if not cognito_id_landlord:
        raise HTTPException(status_code=404, detail="Landlord not found or unauthorized")

    db_house = House(
        name=house.name,
        landlord_id=cognito_id_landlord,
        address=house.address,
        city=house.city,
        state=house.state,
        zipcode=house.zipcode
    )
    
    db.add(db_house)
    db.commit()
    db.refresh(db_house)

    return db_house


# @router.post("/tenents/", response_model=TenentResponse)
# def create_tenent(tenent: TenentCreate, db: Session = Depends(get_db)):
#     db_tenent = Tenents(
#         house_id=tenent.house_id,
#         rent=tenent.rent,
#         tenent_id=tenent.tenent_id
#     )
#     db.add(db_tenent)
#     db.commit()
#     db.refresh(db_tenent)
#     return db_tenent


# Obter todas as casas do landlord
@router.get("/landlord", response_model=List[HouseCreate])
def get_houses_by_landlord(request: Request = None, db: Session = Depends(get_db)):
    
    # Extract access_token from cookies
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    cognito_id_landlord = get_landlord_id_via_kafka(access_token)

    if not cognito_id_landlord:
        raise HTTPException(status_code=404, detail="Landlord not found or unauthorized")

    houses = db.query(House).filter(House.landlord_id == cognito_id_landlord).all()
    if not houses:
        raise HTTPException(status_code=404, detail="Houses not found")
    return houses

# # Obter determinada casa do landlord pelo id da casa e os tenants
# @router.get("/landlord/{landlord_id}/house/{house_id}")
# def get_house_with_tenents(landlord_id: str, house_id: int, db: Session = Depends(get_db)):
#     house = db.query(House).filter(House.landlord_id == landlord_id, House.id == house_id).first()
#     if not house:
#         raise HTTPException(status_code=404, detail="House not found")
    
#     tenents = db.query(Tenents).filter(Tenents.house_id == house_id).all()
    
#     return {
#         "house": house,
#         "tenents": tenents
#     }


# Obter todas as casas de um landlord (Comentar temporariamente)
# @router.get("/landlord/{landlord_id}", response_model=List[schemas.HouseResponse])
# def get_houses_by_landlord(landlord_id: int, db: Session = Depends(database.get_db)):
#     houses = db.query(models.House).filter(models.House.landlord_id == landlord_id).all()
#     if not houses:
#         raise HTTPException(status_code=404, detail="Houses not found")
#     return houses
