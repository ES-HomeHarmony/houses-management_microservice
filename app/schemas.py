from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import date
from fastapi import UploadFile
from typing import List

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
    address: str
    city: str
    state: str
    zipcode: str

    model_config = ConfigDict(from_attributes=True)


# Esquema para criar um inquilino
class TenentCreate(BaseModel):
    house_id: int
    rent: int
    tenent_id: Optional[str] = None
    name: str
    email: str
    contract: Optional[UploadFile] = None

# Esquema para resposta ao criar um inquilino
class TenentResponse(BaseModel):
    id: int
    house_id: int
    rent: int
    tenent_id: str
    contract: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

# Esquema para a criação de uma expense
class ExpenseCreate(BaseModel):
    house_id: int
    amount: float
    title: Optional[str] = None
    description: Optional[str] = None
    deadline_date: Optional[date] = None
    tenant_ids: Optional[List[int]] = None  # IDs of tenants associated with the expense

# Esquema para a criação de um contrato com arquivo
class ContractCreate(BaseModel):
    tenant_id: str

# Esquema para resposta ao criar uma despesa (Expense)
class TenantExpenseDetail(BaseModel):
    tenant_id: int
    status: str  # Status for the specific tenant's share of the expense

class ExpenseResponse(BaseModel):
    id: int
    house_id: int
    amount: float
    title: Optional[str] = None
    description: Optional[str] = None
    created_at: date
    deadline_date: Optional[date] = None
    file_path: Optional[str] = None
    status: str
    tenants: List[TenantExpenseDetail]  # List of tenants associated with the expense, including their statuses

    model_config = ConfigDict(from_attributes=True)

# Esquema para a criação de um issue
class IssueCreate(BaseModel):
    house_id: int
    title: str
    description: str
    status: Optional[str] = None

# Esquema para a edição de um issue
class IssueEdit(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

# Esquema para a resposta ao criar um issue
class IssueResponse(BaseModel):
    id: int
    house_id: int
    tenant_id: Optional[int] = None
    title: str
    description: str
    created_at: date
    status: str

    model_config = ConfigDict(from_attributes=True)