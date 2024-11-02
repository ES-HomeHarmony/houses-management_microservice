from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import House
from app.schemas import HouseCreate, HouseResponse
from typing import List


router = APIRouter(
    prefix="/houses",
    tags=["houses"],
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
