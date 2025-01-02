from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from kafka import KafkaProducer, KafkaConsumer
import os
from app.database import get_db
from app.models import House, Expense, Tenents, TenantExpense
from app.schemas import HouseCreate, HouseResponse, ExpenseCreate, ExpenseResponse, TenentCreate, TenentResponse, TenantExpenseDetail, ContractCreate
from typing import List
from dotenv import load_dotenv
import json
import threading
import time

router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)

# Load environment variables
env = os.getenv('ENV', 'development')
env_file = f'.env/{env}.env'

if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)

# Kafka producer setup
producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Kafka consumer setup
consumer = KafkaConsumer(
    'user-validation-response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='houses_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

tenant_id_cache = {}

# Consumer thread to update tenant ID cache
def start_tenantId_consumer():
    for message in consumer:
        print(message.value)
        tenant_id_cache["cognito_id"] = message.value.get("cognito_id")

threading.Thread(target=start_tenantId_consumer, daemon=True).start()

# Function to retrieve tenant ID via Kafka
def get_tenant_id_via_kafka(access_token: str):
    validation_request = {
        "action": "validate_token",
        "access_token": access_token
    }
    try:
        future = producer.send('user-validation-request', value=validation_request)
        result = future.get(timeout=10)
        print(f"Message sent successfully: {result}")
    except Exception as e:
        print(f"An error occurred: {e}")
    
    cognito_id_tenant = None
    for _ in range(10):
        print(f"Checking for tenant_id in cache: {tenant_id_cache}")
        if "cognito_id" in tenant_id_cache.keys():
            cognito_id_tenant = tenant_id_cache.get("cognito_id")
            print(f"Tenant ID: {cognito_id_tenant}")
            break
        time.sleep(1)
    
    tenant_id_cache.clear()
    if not cognito_id_tenant:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return cognito_id_tenant

# Endpoint to get houses by tenant
@router.get("/houses", response_model=List[HouseResponse])
def get_houses_by_tenant(db: Session = Depends(get_db), request: Request = None):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    tenant_id = get_tenant_id_via_kafka(access_token)
    
    tenant = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    houses = db.query(House).filter(House.id == tenant.house_id).all()
    if not houses:
        raise HTTPException(status_code=404, detail="No houses found for the tenant")
    
    return houses