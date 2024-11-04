from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request
from sqlalchemy.orm import Session
from kafka import KafkaConsumer, KafkaProducer
import json
import threading
import os
from app.database import get_db
from app.models import House, Expense, Tenents, TenantExpense
from app.schemas import HouseCreate, HouseResponse, ExpenseCreate, ExpenseResponse, TenentCreate, TenentResponse, TenantExpenseDetail
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

# Kafka consumer for user creation responses
user_creation_consumer = KafkaConsumer(
    'user-creation-response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='user_creation_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

# Kafka consumer for tenant info responses
tenant_get_info_consumer = KafkaConsumer(
    'tenant_info_response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='tenant_info_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("Kafka consumer initialized and listening...")
print(f"Subscribed topics: {consumer.subscription()}")
print(f"KAFKA_BOOTSTRAP_SERVERS: {os.getenv('KAFKA_BOOTSTRAP_SERVERS')}")

user_cache = {}
user_cache2 = {}
tenant_data_dict = []

# Run the consumer in a separate thread to listen for responses
def start_consumer():
    for message in consumer:
        user_cache["cognito_id"] = message.value.get("cognito_id")
def start_consumer_2():
    for message in user_creation_consumer:
        user_cache2["cognito_id"] = message.value.get("cognito_id")
def start_consumer_3():
    for message in tenant_get_info_consumer:
        tenant_data_dict.append(message.value)

threading.Thread(target=start_consumer, daemon=True).start()
threading.Thread(target=start_consumer_2, daemon=True).start()
threading.Thread(target=start_consumer_3, daemon=True).start()

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
            print(f"Found cognito_id for landlord_id {cognito_id_landlord}")
            break
        time.sleep(1)  # Add a sleep to avoid busy-waiting

    if not cognito_id_landlord:
        raise HTTPException(status_code=404, detail="Landlord not found or unauthorized")

    return cognito_id_landlord

def create_user_in_user_microservice(user_data: dict):
    # Send a message to Kafka for user creation
    user_creation_request = {
        "action": "create_user",
        "user_data": user_data
    }
    
    try:
        future = producer.send('user-creation-request', user_creation_request)
        result = future.get(timeout=10)  # Block until the send is acknowledged or times out
        print(f"Message sent successfully: {result}")
    except Exception as e:
        print(f"Error sending message to Kafka: {e}")

    # Wait for creation response
    cognito_id = None
    for _ in range(10):  # Retry mechanism with limited attempts
        print(f"Checking for cognito_id in cache: {user_cache}")
        
        if "cognito_id" in user_cache2.keys():
            cognito_id = user_cache2.get("cognito_id")
            print(f"Found cognito_id tenant {cognito_id}")
            break
        time.sleep(1)  # Add a sleep to avoid busy-waiting

    if not cognito_id:
        raise HTTPException(status_code=404, detail="User not found or unauthorized")

    return cognito_id

def get_tenant_data(tenant_ids: list):
    # Send a message to Kafka for tenant data
    validation_request = {
        "action": "get_tenants_data",
        "tenant_ids": tenant_ids
    }
    
    try:
        future = producer.send('tenant_info_request', validation_request)
        result = future.get(timeout=10)  # Block until the send is acknowledged or times out
        print(f"Message sent successfully: {result}")
    except Exception as e:
        print(f"Error sending message to Kafka: {e}")

    # Wait for the response
    tenant_data = []
    processed_tenant_ids = set()

    for _ in range(10):  # Retry mechanism with limited attempts
        if tenant_data_dict:
            for tenant_entry in tenant_data_dict:
                for tenant_id, tenant_name in tenant_entry.items():
                    if tenant_id in tenant_ids and tenant_id not in processed_tenant_ids:
                        tenant_data.append({"tenant_id": tenant_id, "name": tenant_name})
                        processed_tenant_ids.add(tenant_id)  # Mark as processed
                        print(f"Found tenant data: {tenant_id} - {tenant_name}")

        time.sleep(1)  # Add a sleep to avoid busy-waiting
    
    tenant_data_dict.clear()  # Clear the cache after processing

    if not tenant_data:
        raise HTTPException(status_code=404, detail="Tenant data not found")

    return tenant_data



def update_expense_status_if_paid(expense_id: int, db: Session):
    # Query all TenantExpense entries related to the given expense
    tenant_expenses = db.query(TenantExpense).filter(TenantExpense.expense_id == expense_id).all()

    # Check if all tenant expenses have a status of 'paid'
    all_paid = all(te.status == 'paid' for te in tenant_expenses)

    if all_paid:
        # If all tenant expenses are marked as paid, update the main expense status
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        if expense:
            expense.status = 'paid'
            db.commit()
            db.refresh(expense)
        else:
            raise HTTPException(status_code=404, detail="Expense not found")
        
def create_tenant_expenses(expense_id: int, house_id: int, db: Session):
    tenants = db.query(Tenents).filter(Tenents.house_id == house_id).all()
    if not tenants:
        raise HTTPException(status_code=404, detail="No tenants found for the given house")

    tenant_expenses = []
    for tenant in tenants:
        tenant_expense = TenantExpense(tenant_id=tenant.id, expense_id=expense_id, status='pending')
        tenant_expenses.append(tenant_expense)

    db.bulk_save_objects(tenant_expenses)
    db.commit()

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


@router.post("/tenents", response_model=TenentResponse)
def create_tenent(tenent: TenentCreate, db: Session = Depends(get_db)):
    
    print(tenent)

    # Create a new user in the user microservice
    user_data = {
        "name": tenent.name,
        "email": tenent.email
    }

    cognito_id = create_user_in_user_microservice(user_data)

    db_tenent = Tenents(
        house_id=tenent.house_id,
        rent=tenent.rent,
        tenent_id=cognito_id
    )

    db.add(db_tenent)
    db.commit()
    db.refresh(db_tenent)
    return db_tenent

# Obter todas as casas do landlord
@router.get("/landlord", response_model=List[HouseResponse])
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
@router.get("/landlord/house/{house_id}")
def get_house_with_tenents(house_id: int, db: Session = Depends(get_db), request: Request = None):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    landlord_id = get_landlord_id_via_kafka(access_token)
    if not landlord_id:
        raise HTTPException(status_code=404, detail="Landlord not found or unauthorized")
    
    house = db.query(House).filter(House.landlord_id == landlord_id, House.id == house_id).first()
    if not house:
        raise HTTPException(status_code=404, detail="House not found")
    
    tenents = db.query(Tenents).filter(Tenents.house_id == house_id).all()
    if not tenents:
        return {"house": house, "tenents": []}  # Return an empty tenant list if none found

    # Collect all cognito IDs to request data for tenants
    list_cognito_ids = [tenent.tenent_id for tenent in tenents]

    # Retrieve tenant data
    tenants_data = get_tenant_data(list_cognito_ids)

    # Structure the tenant data for the response
    structured_tenants = []
    for tenent in tenents:
        tenant_info = next((data for data in tenants_data if data["tenant_id"] == tenent.tenent_id), None)
        if tenant_info:
            structured_tenants.append({
                "tenant_id": tenent.tenent_id,
                "name": tenant_info["name"],
                "email": tenant_info.get("email"),
                "rent": tenent.rent
            })

    # Print structured tenant data for debugging
    print("Structured tenants data:", structured_tenants)

    return {
        "house": house,
        "tenents": structured_tenants
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
        file_path=file_url,
        status="pending"
    )

    db.add(db_expense)
    db.commit()
    db.refresh(db_expense)

    create_tenant_expenses(db_expense.id, db_expense.house_id, db)

    return db_expense


# Obter todas as despesas de uma casa
@router.get("/expenses/{house_id}", response_model=List[ExpenseResponse])
def get_expenses_by_house(house_id: int, db: Session = Depends(get_db)):
    expenses = db.query(Expense).filter(Expense.house_id == house_id).all()
    if not expenses:
        raise HTTPException(status_code=404, detail=f"Expenses not found for house {house_id}")
    return expenses


# @router.get("/expenses/{expense_id}/tenants", response_model=List[TenantExpenseDetail])
# def get_tenant_payment_status(expense_id: int, db: Session = Depends(get_db)):
#     tenant_expenses = db.query(TenantExpense).filter(TenantExpense.expense_id == expense_id).all()

#     if not tenant_expenses:
#         raise HTTPException(status_code=404, detail="No tenant payment details found for this expense")

#     tenant_statuses = [
#         {
#             "tenant_id": te.tenant_id,
#             "status": te.status,
#             "tenant_name": db.query(Tenents).filter(Tenents.id == te.tenant_id).first().tenent_id  # Replace with actual tenant name field
#         }
#         for te in tenant_expenses
#     ]

#     return tenant_statuses


@router.put("/tenants/{tenant_id}/pay")
def mark_tenant_payment(tenant_id: int, expense_id: int, db: Session = Depends(get_db)):
    tenant_expense = db.query(TenantExpense).filter(
        TenantExpense.tenant_id == tenant_id,
        TenantExpense.expense_id == expense_id
    ).first()

    if not tenant_expense:
        raise HTTPException(status_code=404, detail="Tenant expense record not found")

    # Update the tenant's payment status to 'paid'
    tenant_expense.status = 'paid'
    db.commit()

    # Check if the main expense should now be marked as 'paid'
    update_expense_status_if_paid(expense_id, db)

    return {"message": "Tenant payment updated successfully"}

# Endpoint to get a specific expense by its ID
@router.get("/expense/{expense_id}", response_model=ExpenseResponse)
def get_expense_by_id(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    print(expense.__dict__)
    return expense


#delete expenses from a house
@router.delete("/expenses/{expense_id}")
def delete_expense(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    db.delete(expense)
    db.commit()
    return {"message": "Expense deleted successfully"}

@router.put("/expenses/{expense_id}/mark-paid")
def mark_expense_as_paid(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    tenant_expenses = db.query(TenantExpense).filter(TenantExpense.expense_id == expense_id).all()
    all_paid = all(te.status == 'paid' for te in tenant_expenses)

    if all_paid:
        expense.status = 'paid'
        db.commit()
        db.refresh(expense)

    return {"message": "Expense status updated", "status": expense.status}
