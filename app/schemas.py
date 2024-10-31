from pydantic import BaseModel

# Esquema para criar uma casa
class HouseCreate(BaseModel):
    name: str
    tenants_count: int
    landlord_id: str  

# Esquema para resposta ao criar uma casa
class HouseResponse(BaseModel):
    id: int
    name: str
    tenants_count: int
    landlord_id: str

    class Config:
        orm_mode = True
