from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from kafka import KafkaConsumer
import json
from .. import models, database, schemas
import threading
import os

router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"],
)

# consumer = KafkaConsumer(
#     'user_topic',
#     bootstrap_servers=['localhost:9092'],
#     value_deserializer=lambda x: json.loads(x.decode('utf-8'))
# )
print("Attempting to connect to Kafka at:", os.getenv('KAFKA_BOOTSTRAP_SERVERS'))
consumer = KafkaConsumer(
    'user-topic',
    bootstrap_servers='kafka:9092',
    auto_offset_reset='earliest',
    group_id='landlord_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)
print("Connected to Kafka")

# Cache temporário para armazenar cognito_id
user_cache = {}

def cache_user_cognito_ids():
    """Consumes messages from Kafka and populates the user cache."""
    for message in consumer:
        user_data = message.value
        cognito_id = user_data.get("cognito_id")
        if cognito_id:
            user_cache[cognito_id] = user_data
            print(f"Cached user data for cognito_id {cognito_id}: {user_data}")

# Executa o consumidor em uma thread separada
threading.Thread(target=cache_user_cognito_ids, daemon=True).start()

@router.post("/create", response_model=schemas.HouseResponse)
def create_house(house: schemas.HouseCreate, db: Session = Depends(database.get_db)):
    landlord_id = house.landlord_id
    
    # Ensure that the landlord's cognito_id exists in the cache
    if landlord_id not in user_cache:
        raise HTTPException(status_code=404, detail="Landlord not found in user service")

    # Proceed to create the house entry in the database
    db_house = models.House(
        name=house.name,
        tenants_count=house.tenants_count,
        landlord_id=landlord_id
    )
    db.add(db_house)
    db.commit()
    db.refresh(db_house)
    return db_house