from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request
from sqlalchemy.orm import Session
from kafka import KafkaConsumer, KafkaProducer
import json
import threading
import os
from app.database import get_db
from app.models import House, Expense, Tenents
from app.schemas import HouseCreate, HouseResponse, ExpenseCreate, ExpenseResponse, TenentCreate, TenentResponse
from typing import List
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError
import os
from dotenv import load_dotenv
import json
from fastapi.responses import JSONResponse
import time


router = APIRouter(
    prefix="/houses",
    tags=["houses"],
)


env = os.getenv('ENV', 'development')
env_file = f'.env/{env}.env'

# Load environment variables from file
if os.path.exists(env_file):
    load_dotenv(env_file)

s3_client = boto3.client(
    "s3",
    region_name=os.getenv("S3_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
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

# Criar uma casa para um landlord
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


@router.post("/tenents/", response_model=TenentResponse)
def create_tenent(tenent: TenentCreate, db: Session = Depends(get_db)):
    db_tenent = Tenents(
        house_id=tenent.house_id,
        rent=tenent.rent,
        tenent_id=tenent.tenent_id
    )
    db.add(db_tenent)
    db.commit()
    db.refresh(db_tenent)
    return db_tenent


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

# Obter determinada casa do landlord pelo id da casa e os tenants
@router.get("/landlord//house/{house_id}")
def get_house_with_tenents(landlord_id: str, house_id: int, db: Session = Depends(get_db)):
    house = db.query(House).filter(House.landlord_id == landlord_id, House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")
    
    tenents = db.query(Tenents).filter(Tenents.house_id == house_id).all()
    
    return {
        "house": house,
        "tenents": tenents
    }


# Fazer post de uma nova despesa para uma casa
@router.post("/addExpense", response_model=ExpenseResponse)
def add_expense(expense_data: str = Form(...), file: UploadFile = File(...),db: Session = Depends(get_db)):
    
    # Parse the JSON string into the ExpenseCreate model
    try:
        expense = ExpenseCreate(**json.loads(expense_data))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    file_url = None

    if file:
        try:
            s3_client.upload_fileobj(
                file.file,
                os.getenv("S3_BUCKET"),
                f"expenses/{file.filename}"
            )
            file_url = f"https://{os.getenv('S3_BUCKET')}.s3.{os.getenv('S3_REGION')}.amazonaws.com/expenses/{file.filename}"
        except NoCredentialsError:
            return JSONResponse(status_code=400, content={"error": "Credenciais não encontradas"})
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": str(e)})
    
    db_expense = Expense(
        house_id=expense.house_id,
        amount=expense.amount,
        title=expense.title,
        description=expense.description,
        created_at=datetime.now(),
        deadline_date=expense.deadline_date,
        file_path=file_url
    )

    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)
    return db_expense


# Obter todas as despesas de uma casa
@router.get("/expenses/{house_id}", response_model=List[ExpenseResponse])
def get_expenses_by_house(house_id: int, db: Session = Depends(get_db)):
    expenses = db.query(Expense).filter(Expense.house_id == house_id).all()
    if not expenses:
        raise HTTPException(status_code=404, detail=f"Expenses not found for house {house_id}")
    return expenses