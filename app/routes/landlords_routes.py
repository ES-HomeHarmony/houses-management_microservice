from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Request, BackgroundTasks
from sqlalchemy.orm import Session
import json
import os
from app.database import get_db
from app.models import House, Expense, Tenents, TenantExpense
from app.schemas import HouseCreate, HouseResponse, ExpenseCreate, ExpenseResponse, TenentCreate, TenentResponse, TenantExpenseDetail, ContractCreate
from typing import List
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError
import os
from dotenv import load_dotenv
import json
from fastapi.responses import JSONResponse, StreamingResponse
import time
from urllib.parse import unquote
import requests
import unicodedata
from app.services.kafka import user_cache, user_cache2, tenant_data_dict, producer, consumer, user_creation_consumer, tenant_get_info_consumer
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("house_service_landlord")

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

def get_landlord_id_via_kafka(access_token: str):
    # Send a message to Kafka for user validation
    validation_request = {
        "action": "validate_token",
        "access_token": access_token
    }
    
    try:
        future = producer.send('user-validation-request', validation_request)
        result = future.get(timeout=10)  # Block until the send is acknowledged or times out
        logger.info(f"Message sent successfully: {result}")
    except Exception as e:
        logger.info(f"Error sending message to Kafka: {e}")

    # Wait for validation response
    cognito_id_landlord = None
    for _ in range(10):  # Retry mechanism with limited attempts
        
        if "cognito_id" in user_cache.keys():
            cognito_id_landlord = user_cache.get("cognito_id")
            logger.info(f"Found cognito_id for landlord_id {cognito_id_landlord}")
            break
        time.sleep(1)  # Add a sleep to avoid busy-waiting
    
    user_cache.clear()  # Clear the cache after processing

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
        logger.info(f"Message sent successfully: {result}")
        producer.send('invite-request', user_creation_request)
    except Exception as e:
        logger.info(f"Error sending message to Kafka: {e}")

    # Wait for creation response
    cognito_id = None
    for _ in range(10):  # Retry mechanism with limited attempts        
        if "cognito_id" in user_cache2.keys():
            cognito_id = user_cache2.get("cognito_id")
            logger.info(f"Found cognito_id tenant {cognito_id}")
            break
        time.sleep(1)  # Add a sleep to avoid busy-waiting

    user_cache2.clear()  # Clear the cache after processing

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
        logger.info(f"Message sent successfully: {result}")
    except Exception as e:
        logger.info(f"Error sending message to Kafka: {e}")

    # Wait for the response
    tenant_data = []
    processed_tenant_ids = set()

    logger.info(f"Waiting for tenant data...{tenant_ids}")
    for _ in range(7): 
        if tenant_data_dict:
            for tenant_entry in tenant_data_dict:
                for tenant_id in tenant_entry.keys():
                    if tenant_id in tenant_ids and tenant_id not in processed_tenant_ids:
                        
                        tenant_name = tenant_entry.get(tenant_id)[0]
                        tenant_email = tenant_entry.get(tenant_id)[1]
                        
                        tenant_data.append({"tenant_id": tenant_id, "name": tenant_name, "email": tenant_email})
                        
                        processed_tenant_ids.add(tenant_id)  # Mark as processed
                        logger.info(f"Found tenant data: {tenant_id}: {tenant_name} - {tenant_email}")

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
        
def create_tenant_expenses(expense: Expense, db: Session):
    
    # Validar se o valor do montante é válido
    if expense.amount is None or not isinstance(expense.amount, (int, float)):
        raise HTTPException(status_code=400, detail="Expense amount cannot be null or non-numeric")

    if expense.amount < 0:
        raise HTTPException(status_code=400, detail="Expense amount cannot be negative")

    # Validar se o house_id é válido
    if expense.house_id is None or not isinstance(expense.house_id, int):
        raise HTTPException(status_code=400, detail="House ID cannot be null or invalid")

    tenants = db.query(Tenents).filter(Tenents.house_id == expense.house_id).all()
    if not tenants:
        raise HTTPException(status_code=404, detail="No tenants found for the given house")

    # Garantir unicidade de tenants
    unique_tenants = list({tenant.id: tenant for tenant in tenants}.values())

    num_tenants = len(unique_tenants)
    if num_tenants == 0:
        raise HTTPException(status_code=400, detail="No tenants available for expense division")

    if expense.amount < 0.1:
        share_per_tenant = 0.0
        last_share = expense.amount
    else:
        share_per_tenant = round(expense.amount / num_tenants, 1)
        total_allocated = round(share_per_tenant * (num_tenants - 1), 1)
        last_share = round(expense.amount - total_allocated, 1)

    tenant_expenses = []
    for i, tenant in enumerate(unique_tenants):
        amount = share_per_tenant if i < num_tenants - 1 else last_share
        tenant_expense = TenantExpense(
            tenant_id=tenant.id,
            expense_id=expense.id,
            status='pending',
            amount=amount,
        )
        tenant_expenses.append(tenant_expense)

    db.bulk_save_objects(tenant_expenses)
    db.commit()

    return tenant_expenses[0].amount


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
    
    logger.info(tenent)

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
    
    tenants = db.query(Tenents).filter(Tenents.house_id == house_id).all()
    if not tenants:
        return {"house": house, "tenants": []}  # Return an empty tenant list if none found

    # Collect all cognito IDs to request data for tenants
    list_cognito_ids = [tenant.tenent_id for tenant in tenants]

    # Retrieve tenant data
    tenants_data = get_tenant_data(list_cognito_ids)

    # Structure the tenant data for the response
    structured_tenants = []
    for tenant in tenants:
        tenant_info = next((data for data in tenants_data if data["tenant_id"] == tenant.tenent_id), None)
        if tenant_info:
            structured_tenants.append({
                "tenant_id": tenant.tenent_id,
                "name": tenant_info["name"],
                "email": tenant_info["email"],
                "rent": tenant.rent,
                "contract": tenant.contract
            })

    # Print structured tenant data for debugging
    logger.info("Structured tenants data:", structured_tenants)

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

            if " " in file.filename:
                file.filename = file.filename.replace(" ", "_")

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

    # Automatically divide the expense among tenants
    bill = create_tenant_expenses(db_expense, db)

    #Ir buscar os tenants para enviar o email
    tenants= db.query(Tenents).filter(Tenents.house_id == expense.house_id).all()
    # Lista para armazenar os dados dos inquilinos
    user_data_list = []

    for tenant in tenants:
        tenant_data = [tenant.tenent_id]
        tenants_data = get_tenant_data(tenant_data)
        
        user_data_list.append({
            "email": tenants_data[0]["email"],
            "name": tenants_data[0]["name"]
        })

    # Cria a mensagem única
    message = {
        "action": "expense_created",
        "user_data": {
            "expense_details": {
                "title": expense.title,
                "amount": bill,
                "deadline_date": expense.deadline_date.strftime('%Y-%m-%d')
            },
            "users": user_data_list
        }
    }

    logger.info(message)
    producer.send('invite-request', message)

        
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
def mark_tenant_payment(tenant_id: int, expense_id: int, db: Session = Depends(get_db),background_tasks: BackgroundTasks = None):
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

    #Notificar o senhorio que o inquilino pagou assicronamente
    #Procurar a casa
     # Adiciona a tarefa em segundo plano
    background_tasks.add_task(
        notify_paid,
        db=db,
        expense_id=expense_id,
        tenant_id=tenant_id
    )

    return {"message": "Tenant payment updated successfully"}

def notify_paid(db: Session, expense_id: int, tenant_id: int):
    logger.info("Notifying landlord that tenant paid...")
    tenant = db.query(Tenents).filter(Tenents.id == tenant_id).first()
    house = db.query(House).filter(House.id == tenant.house_id).first()
    landlord_id = house.landlord_id
    landlord_data = [landlord_id]
    landlord_data = get_tenant_data(landlord_data)
    tenant_data = [tenant.tenent_id]
    tenants_data = get_tenant_data(tenant_data)
    message = {
        "action": "tenant_paid",
        "user_data": {
            "email": landlord_data[0]["email"],
            "name": landlord_data[0]["name"],
            "tenant_name": tenants_data[0]["name"],
            "expense_name": db.query(Expense).filter(Expense.id == expense_id).first().title,
            "amount": db.query(TenantExpense).filter(Tenents.id == tenant_id, TenantExpense.expense_id == expense_id).first().amount,
            "house_name": house.name
            
        }
    }
    producer.send('invite-request', message)



# Endpoint to get a specific expense by its ID
# @router.get("/expense/{expense_id}", response_model=ExpenseResponse)
# def get_expense_by_id(expense_id: int, db: Session = Depends(get_db)):
#     expense = db.query(Expense).filter(Expense.id == expense_id).first()
#     if not expense:
#         raise HTTPException(status_code=404, detail="Expense not found")
#     print(expense.__dict__)
#     return expense

@router.get("/expense/{expense_id}", response_model=ExpenseResponse)
def get_expense_by_id(expense_id: int, db: Session = Depends(get_db)):
    # Fetch the expense
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")

    # Fetch tenant payment statuses for the expense
    tenant_expenses = db.query(TenantExpense).filter(TenantExpense.expense_id == expense_id).all()

    # if not tenant_expenses:
    #     return {
    #         "id": expense.id,
    #         "house_id": expense.house_id,
    #         "amount": expense.amount,
    #         "title": expense.title,
    #         "description": expense.description,
    #         "created_at": expense.created_at,
    #         "deadline_date": expense.deadline_date,
    #         "file_path": expense.file_path,
    #         "status": expense.status,
    #         "tenants": []  # Return an empty list if there are no tenants
    #     }

    # Fetch Cognito IDs for the tenants
    tenant_ids = [te.tenant_id for te in tenant_expenses]
    tenant_records = db.query(Tenents).filter(Tenents.id.in_(tenant_ids)).all()

    if not tenant_records:
        raise HTTPException(status_code=404, detail="Tenants not found")

    cognito_ids = [tenant.tenent_id for tenant in tenant_records]
    print("Cognito IDs:", cognito_ids)

    for tenant in tenant_records:
        logger.info(tenant.__dict__)
    # Fetch tenant data (name and email) using the Cognito IDs
    tenant_data = get_tenant_data(cognito_ids)

    # Combine tenant payment statuses with tenant details
    tenants = [
        {
            "tenant_id": te.tenant_id,
            "status": te.status,
            "tenant_name": next(
                (tenant["name"] for tenant in tenant_data if tenant["tenant_id"] == tenant_record.tenent_id),
                "Unknown"  # Default to "Unknown" if no name is found
            )
        }
        for te in tenant_expenses
        for tenant_record in tenant_records
        if te.tenant_id == tenant_record.id
    ]

    # Build the response
    response = {
        "id": expense.id,
        "house_id": expense.house_id,
        "amount": expense.amount,
        "title": expense.title,
        "description": expense.description,
        "created_at": expense.created_at,
        "deadline_date": expense.deadline_date,
        "file_path": expense.file_path,
        "status": expense.status,
        "tenants": tenants
    }

    return response



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

@router.post("/uploadContract")
def upload_contract(contract_data: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    file_url = None

    # Parse the JSON string into the ExpenseCreate model
    try:
        contract_create = ContractCreate(**json.loads(contract_data))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    if file:
        try:

            if " " in file.filename:
                file.filename = file.filename.replace(" ", "_")

            s3_client.upload_fileobj(
                file.file,
                os.getenv("S3_BUCKET"),
                f"contracts/{file.filename}"
            )

            logger.info(f"File uploaded successfully")

            file_url = f"https://{os.getenv('S3_BUCKET')}.s3.{os.getenv('S3_REGION')}.amazonaws.com/contracts/{file.filename}"
        
        except NoCredentialsError:
            return JSONResponse(status_code=400, content={"error": "Credenciais não encontradas"})
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": str(e)})
        
    tenant = db.query(Tenents).filter(Tenents.tenent_id == contract_create.tenant_id).first()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    tenant.contract = file_url
    db.commit()
    db.refresh(tenant)

    tenant_data = [contract_create.tenant_id]
    tenants_data = get_tenant_data(tenant_data)
    message = {
        "action": "upload_contract",
        "user_data": {
        "email": tenants_data[0]["email"],
        "name": tenants_data[0]["name"]
        }
    }
    logger.info(message)
    producer.send('invite-request', message)

    return {"message": "Contract uploaded successfully", "file_url": file_url}

def normalize_filename(filename: str) -> str:
    # Remover acentos e caracteres especiais
    return unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")

@router.get("/expenses/{expense_id}/download")
def download_expense_file(expense_id: int, db: Session = Depends(get_db)):
    # Obter a despesa do banco de dados
    expense = db.query(Expense).filter(Expense.id == expense_id).first()
    if not expense or not expense.file_path:
        raise HTTPException(status_code=404, detail="File URL not found in database")

    # Decodificar a URL com caracteres especiais
    file_url = unquote(expense.file_path)
    logger.info(f"Downloading file from URL: {file_url}")

    try:
        # Fazer a requisição HTTP ao S3 para buscar o arquivo
        response = requests.get(file_url, stream=True)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch file from S3")

        # Obter o nome do arquivo da URL e normalizar
        file_name = file_url.split("/")[-1]
        normalized_file_name = normalize_filename(file_name)

        # Retornar o arquivo como resposta de streaming
        return StreamingResponse(
            response.iter_content(chunk_size=1024),  # Envia o conteúdo em chunks
            media_type="application/pdf",           # Tipo MIME como PDF
            headers={
                # O cabeçalho 'inline' permite que o PDF seja exibido no navegador
                "Content-Disposition": f"inline; filename={normalized_file_name}"
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

        