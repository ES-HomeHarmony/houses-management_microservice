from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from kafka import KafkaConsumer
import json
from .. import models, database, schemas
import threading
import os
from app.database import get_db
from app.models import House
from app.schemas import HouseCreate, HouseResponse
from typing import List


router = APIRouter(
    prefix="/houses",
    tags=["houses"],
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

@router.post("/create", response_model=HouseResponse)
def create_house(house: schemas.HouseCreate, db: Session = Depends(database.get_db)):
    landlord_id = house.landlord_id
    
    # Ensure that the landlord's cognito_id exists in the cache
    if landlord_id not in user_cache:
        raise HTTPException(status_code=404, detail="Landlord not found in user service")

    db_house = House(
        name=house.name,
        landlord_id=house.landlord_id,
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
@router.get("/landlord/{landlord_id}", response_model=List[HouseCreate])
def get_houses_by_landlord(landlord_id: str, db: Session = Depends(get_db)):
    houses = db.query(House).filter(House.landlord_id == landlord_id).all()
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
