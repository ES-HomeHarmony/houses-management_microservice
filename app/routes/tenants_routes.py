from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from kafka import KafkaProducer, KafkaConsumer
import os
from app.database import get_db
from app.models import Tenents, Issue
from app.schemas import IssueCreate, IssueResponse, IssueEdit
import os
import time
from app.services.kafka import user_cache, producer


router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)


def get_tenant_id_via_kafka(access_token: str):

    validation_request = {
        "action": "validate_token",
        "access_token": access_token
    }

    try:
        future = producer.send('user-validation-request', value=validation_request)
        result = future.get(timeout=10)
        print(f"Message sent successfully: {result}")
    except Exception as e:
        print(f"An error occurred: {e}")

    cognito_id_tenant = None

    for _ in range(10):
        
        print(f"Checking for tenant_id in cache: {user_cache}")
        if "cognito_id" in user_cache.keys():
            cognito_id_tenant = user_cache.get("cognito_id")
            print(f"Tenant ID: {cognito_id_tenant}")
            break
        
        time.sleep(1)
    
    user_cache.clear()

    if not cognito_id_tenant:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return cognito_id_tenant


@router.post("/createIssue", response_model=IssueResponse)
def create_issue(issue: IssueCreate, db: Session = Depends(get_db), request: Request = None):

    # Extract access_token from cookies
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    # Get tenant_id from access_token
    tenant_id = get_tenant_id_via_kafka(access_token)

    # Get Tenant
    tenant = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
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
    return new_issue

@router.put("/updateIssue", response_model=IssueResponse)
def update_issue(issue: IssueEdit, db: Session = Depends(get_db), request: Request = None):
    
    # Extract access_token from cookies
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(status_code=401, detail="Access token missing")
    
    # Get tenant_id from access_token
    tenant_id = get_tenant_id_via_kafka(access_token)

    # Get Tenant
    tenant = db.query(Tenents).filter(Tenents.tenent_id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    issue = db.query(Issue).filter(Issue.id == issue.id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.tenant_id != tenant.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    issue.title = issue.title if issue.title else issue.title
    issue.description = issue.description if issue.description else issue.description
    issue.status = issue.status if issue.status else issue.status
    issue.priority = issue.priority if issue.priority else issue.priority

    db.commit()
    db.refresh(issue)
    return issue
