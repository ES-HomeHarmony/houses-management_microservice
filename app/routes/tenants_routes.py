from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from kafka import KafkaProducer, KafkaConsumer
import os
from app.database import get_db
from app.models import Tenents, Issue
from app.schemas import IssueCreate, IssueResponse, IssueEdit
import os
from dotenv import load_dotenv
import json
import threading
import time


router = APIRouter(
    prefix="/tenants",
    tags=["tenants"],
)

env = os.getenv('ENV', 'development')
env_file = f'.env/{env}.env'

if os.path.exists(env_file):
    load_dotenv(dotenv_path=env_file)


producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Kafka consumer for receiving responses
consumer = KafkaConsumer(
    'user-validation-response',
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS'),
    auto_offset_reset='earliest',
    group_id='houses_group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

tenant_id_cache = {}

def start_tenantId_consumer():
    for message in consumer:
        print(message.value)
        tenant_id_cache["cognito_id"] = message.value.get("cognito_id")


threading.Thread(target=start_tenantId_consumer).start()

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
        
        print(f"Checking for tenant_id in cache: {tenant_id_cache}")
        if "cognito_id" in tenant_id_cache.keys():
            cognito_id_tenant = tenant_id_cache.get("cognito_id")
            print(f"Tenant ID: {cognito_id_tenant}")
            break
        
        time.sleep(1)
    
    tenant_id_cache.clear()

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
