from pydantic import BaseModel, ConfigDict

# Esquema para criar uma casa
class HouseCreate(BaseModel):
    name: str
    landlord_id: str
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