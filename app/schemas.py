from pydantic import BaseModel

# Esquema para criar uma casa
class HouseCreate(BaseModel):
    name: str
    tenants_count: int
    # landlord_id: int  # Comentar temporariamente

# Esquema para resposta ao criar uma casa
class HouseResponse(BaseModel):
    id: int
    name: str
    tenants_count: int
    # landlord_id: int  # Comentar temporariamente

    class Config:
        orm_mode = True
