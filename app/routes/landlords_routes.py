from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, database, schemas

router = APIRouter(
    prefix="/expenses",
    tags=["Expenses"],
)

@router.post("/create", response_model=schemas.HouseResponse)
def create_house(house: schemas.HouseCreate, db: Session = Depends(database.get_db)):
    db_house = models.House(**house.dict())
    db.add(db_house)
    db.commit()
    db.refresh(db_house)
    return db_house

@router.get("/landlord/{landlord_id}", response_model=List[schemas.HouseResponse])
def get_houses_by_landlord(landlord_id: int, db: Session = Depends(database.get_db)):
    houses = db.query(models.House).filter(models.House.landlord_id == landlord_id).all()
    if not houses:
        raise HTTPException(status_code=404, detail="Houses not found")
    return houses
