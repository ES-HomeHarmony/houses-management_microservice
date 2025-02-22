import requests
from fastapi.responses import StreamingResponse
from app.routes.landlords_routes import normalize_filename
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.kafka import user_cache, producer
from app.models import House, Tenents, Issue
from app.schemas import HouseResponse, IssueCreate, IssueResponse, IssueEdit, TenentResponse
from typing import List
import time
from urllib.parse import unquote
from app.routes.landlords_routes import get_tenant_data
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("house_service_tenant")


router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)


DETAIL = "Tenant not found"

def get_tenant_id_via_kafka(access_token: str):

    validation_request = {
        "action": "validate_token",
        "access_token": access_token
    }

    try:
        future = producer.send('user-validation-request', value=validation_request)
        result = future.get(timeout=10)
        logger.info(f"Message sent successfully: {result}")
    except Exception as e:
        logger.info(f"An error occurred: {e}")

    cognito_id_tenant = None

    for _ in range(10):
        if "cognito_id" in user_cache.keys():
            cognito_id_tenant = user_cache.get("cognito_id")
            logger.info(f"Tenant ID: {cognito_id_tenant}")
            break
        
        time.sleep(1)
    
    user_cache.clear()

    if not cognito_id_tenant:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return cognito_id_tenant

def tenant_update_id(old_id, new_id, db: Session):

    tenant = db.query(Tenents).filter(Tenents.tenent_id == old_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=DETAIL)
    
    tenant.tenent_id = new_id
    db.commit()
    db.refresh(tenant)
    logger.info(f"Tenant ID updated: {tenant}")
    return

@router.post("/createIssue", response_model=IssueResponse)
def create_issue(issue: IssueCreate, db: Session = Depends(get_db), request: Request = None, background_tasks: BackgroundTasks = None):

    # Extract access_token from cookies
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    # Get tenant_id from access_token
    tenant_id = get_tenant_id_via_kafka(access_token)

    # Get Tenant
    tenant = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=DETAIL)
    
    new_issue = Issue(
        house_id=issue.house_id,
        tenant_id=tenant.id,
        title=issue.title,
        description=issue.description,
        status=issue.status,
        priority=issue.priority
    )
    
    db.add(new_issue)
    db.commit()
    db.refresh(new_issue)

    logger.info(f"New issue created: {new_issue}")

    # Adiciona a tarefa em segundo plano
    background_tasks.add_task(
        notify_kafka,
        db=db,
        issue=issue,
        tenant_id=tenant_id
    )

    return new_issue

def notify_kafka(db: Session, issue: IssueCreate, tenant_id: str):
    logger.info(f"Notify Kafka: {issue}")
    landlord_id = db.query(House).filter(House.id == issue.house_id).first().landlord_id
    landlord_data = get_tenant_data([landlord_id])
    tenant_main = get_tenant_data([tenant_id])
    tenants = db.query(Tenents).filter(Tenents.house_id == issue.house_id).all()

    user_data_list = []
    house_details = db.query(House).filter(House.id == issue.house_id).first()

    for tenant in tenants:
        tenant_data = [tenant.tenent_id]
        tenants_data = get_tenant_data(tenant_data)
        
        user_data_list.append({
            "email": tenants_data[0]["email"],
            "name": tenants_data[0]["name"]
        })

    user_data_list.append({
        "email": landlord_data[0]["email"],
        "name": landlord_data[0]["name"]
    })

    message = {
        "action": "new_issue",
        "user_data":{
            "issue": {
                "title": issue.title,
                "description": issue.description,
                "status": issue.status,
                "priority": issue.priority
            },
            "house_name": house_details.name,
            "tenant_name": tenant_main[0]["name"],
            "users": user_data_list
        }
    }

    # Aqui você enviaria a mensagem ao Kafka
    logger.info(f"Message to be sent: {message}")
    producer.send("invite-request", message)

@router.put("/updateIssue", response_model=IssueResponse)
def update_issue(issue: IssueEdit, db: Session = Depends(get_db), request: Request = None):
    # Extract access_token from cookies
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
       
    existing_issue = db.query(Issue).filter(Issue.id == issue.id).first()
    if not existing_issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Update fields only if new values are provided
    if issue.title:
        existing_issue.title = issue.title
    if issue.description:
        existing_issue.description = issue.description
    if issue.status:
        existing_issue.status = issue.status
    if issue.priority:
        existing_issue.priority = issue.priority

    db.commit()
    db.refresh(existing_issue)
    logger.info(f"Issue updated: {existing_issue}")
    return existing_issue

# Endpoint to get houses by tenant
@router.get("/houses", response_model=List[HouseResponse])
def get_houses_by_tenant(db: Session = Depends(get_db), request: Request = None):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")

    tenant_id = get_tenant_id_via_kafka(access_token)

    tenants = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).all()
    
    if not tenants:
        raise HTTPException(status_code=404, detail=DETAIL)
    
    houses = []

    for tenant in tenants:
        houses += db.query(House).filter(House.id == tenant.house_id).all()

    if not houses:
        raise HTTPException(status_code=404, detail="No houses found for the tenant")

    return houses

@router.get("/houses/{house_id}/issues", response_model=List[IssueResponse])
def get_issues_by_house(house_id: int, db: Session = Depends(get_db)):
    issues = db.query(Issue).filter(Issue.house_id == house_id).all()
    if not issues:
        return []
    
    # Converter explicitamente para o esquema Pydantic
    return [IssueResponse.model_validate(issue) for issue in issues]

@router.get("/issues/{issue_id}", response_model=IssueResponse)
def get_issue_by_id(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue

@router.get("/landlords/{landlord_id}/issues", response_model=List[IssueResponse])
def get_issues_by_landlord(landlord_id: str, db: Session = Depends(get_db)):
    houses = db.query(House).filter(House.landlord_id == landlord_id).all()
    if not houses:
        raise HTTPException(status_code=404, detail=f"No houses found for landlord {landlord_id}")
    
    house_ids = [house.id for house in houses]
    issues = db.query(Issue).filter(Issue.house_id.in_(house_ids)).all()
    if not issues:
        raise HTTPException(status_code=404, detail=f"No issues found for landlord {landlord_id}")
    return issues

@router.delete("/issues/{issue_id}")
def delete_issue(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    db.delete(issue)
    db.commit()
    logger.info(f"Issue deleted: {issue}")
    return {"message": "Issue deleted successfully"}

@router.get("/downloadContract")
def download_expense_file(db: Session = Depends(get_db), request: Request = None):
    
    access_token = request.cookies.get("access_token")

    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    tenant_id = get_tenant_id_via_kafka(access_token)

    tenant = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).first()

    if not tenant:
        raise HTTPException(status_code=404, detail=DETAIL)

    # Decodificar a URL com caracteres especiais
    file_url = unquote(tenant.contract)
    print(f"Downloading file from URL: {file_url}")

    try:
        # Fazer a requisição HTTP ao S3 para buscar o arquivo
        response = requests.get(file_url, stream=True)
        if response.status_code != 200:
            raise HTTPException(status_code=404, detail="Failed to fetch file from S3")

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
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
# Get tenant id in the tenents table
@router.get("/tenantId", response_model=TenentResponse)
def get_tenant_id(request: Request = None, db: Session = Depends(get_db)):
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")

    tenant_id = get_tenant_id_via_kafka(access_token)

    tenant = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail=DETAIL)
    return tenant
