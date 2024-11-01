from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import House, Expense
from app.schemas import HouseCreate, HouseResponse, ExpenseCreate, ExpenseResponse
from typing import List
from datetime import datetime
import boto3
from botocore.exceptions import NoCredentialsError
import os
from dotenv import load_dotenv
import json


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

# Criar uma casa para um landlord
@router.post("/create", response_model=HouseResponse)
def create_house(house: HouseCreate, db: Session = Depends(get_db)):
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


# Fazer post de uma nova despesa para uma casa
@router.post("/addExpense", response_model=ExpenseResponse)
def add_expense(expense_data: str = Form(...), file: UploadFile = File(...),db: Session = Depends(get_db)):
    
    # Parse the JSON string into the ExpenseCreate model
    try:
        expense = ExpenseCreate(**json.loads(expense_data))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    fileURL = None

    if file:
        try:
            s3_client.upload_fileobj(
                file.file,
                os.getenv("S3_BUCKET"),
                f"expenses/{file.filename}"
            )
            fileURL = f"https://{os.getenv('S3_BUCKET')}.s3.{os.getenv('S3_REGION')}.amazonaws.com/expenses/{file.filename}"
        except NoCredentialsError:
            return {"error": "Credenciais não encontradas"}
        except Exception as e:
            return {"error": str(e)}
    
    db_expense = Expense(
        house_id=expense.house_id,
        amount=expense.amount,
        title=expense.title,
        description=expense.description,
        created_at=datetime.now(),
        deadline_date=expense.deadline_date,
        file_path=fileURL
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