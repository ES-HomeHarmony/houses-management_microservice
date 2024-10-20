from pydantic import BaseModel
from typing import List, Optional

# Esquema para criar uma casa
class HouseCreate(BaseModel):
    name: str
    tenants_count: int
    landlord_id: int

# Esquema para resposta ao criar uma casa
class HouseResponse(BaseModel):
    id: int
    name: str
    tenants_count: int
    landlord_id: int

    class Config:
        orm_mode = True

# Esquema para criar um landlord
class LandlordCreate(BaseModel):
    name: str
    email: str

# Esquema para resposta ao criar um landlord
class LandlordResponse(BaseModel):
    id: int
    name: str
    email: str
    houses: List[HouseResponse] = []

    class Config:
        orm_mode = True
