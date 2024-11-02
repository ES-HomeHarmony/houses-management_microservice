from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date
from fastapi import UploadFile

# Esquema para criar uma casa
class HouseCreate(BaseModel):
    name: str
    address: str
    city: str
    state: str
    zipcode: str


# Esquema para resposta ao criar uma casa
class HouseResponse(BaseModel):
    id: int
    name: str
    landlord_id: str

    model_config = ConfigDict(from_attributes=True)


# # Esquema para criar um inquilino
# class TenentCreate(BaseModel):
#     house_id: int
#     rent: int
#     tenent_id: str

# # Esquema para resposta ao criar um inquilino
# class TenentResponse(BaseModel):
#     id: int
#     house_id: int
#     rent: int
#     tenent_id: str

#     model_config = ConfigDict(from_attributes=True)

# Esquema para a criação de uma expense
class ExpenseCreate(BaseModel):
    house_id: int
    amount: float
    title: Optional[str] = None
    description: Optional[str] = None
    deadline_date: Optional[date] = None

# Esquema para a resposta ao criar uma expense
class ExpenseResponse(BaseModel):
    id: int
    house_id: int
    amount: float
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: date
    deadline_date: Optional[date] = None
    file_path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)