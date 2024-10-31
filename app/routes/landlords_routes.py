from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from kafka import KafkaConsumer
import json
from .. import models, database, schemas
import threading

router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"],
)

# consumer = KafkaConsumer(
#     'user_topic',
#     bootstrap_servers=['localhost:9092'],
#     value_deserializer=lambda x: json.loads(x.decode('utf-8'))
# )

consumer = KafkaConsumer(
    'user-topic',
    bootstrap_servers='kafka:9092',
    auto_offset_reset='earliest',
    group_id='landlord_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

# Cache temporário para armazenar cognito_id
user_cache = {}

def cache_user_cognito_ids():
    for message in consumer:
        user_data = message.value
        cognito_id = user_data.get("cognito_id")
        if cognito_id:
            user_cache[cognito_id] = user_data
        print(f"Received user data from Kafka: {user_data}")

def consume_messages():
    for message in consumer:
        user_data = message.value
        print(f"Mensagem recebida do Kafka: {user_data}")

# Executa o consumidor em uma thread separada
threading.Thread(target=cache_user_cognito_ids, daemon=True).start()

# Executa o consumidor em uma thread separada
threading.Thread(target=consume_messages).start()

@router.post("/create", response_model=schemas.HouseResponse)
def create_house(house: schemas.HouseCreate, db: Session = Depends(database.get_db)):
    landlord_id = house.landlord_id
    if landlord_id not in user_cache:
        raise HTTPException(status_code=404, detail="Landlord not found in user service")

    db_house = models.House(
        name=house.name,
        tenants_count=house.tenants_count,
        landlord_id=landlord_id
    )
    db.add(db_house)
    db.commit()
    db.refresh(db_house)
    return db_house