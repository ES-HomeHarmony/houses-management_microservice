from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import landlords_routes, tenants_routes
from app.database import Base, engine

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cria todas as tabelas no DB
Base.metadata.create_all(bind=engine)

# Incluir os endpoints relacionados a expenses
app.include_router(landlords_routes.router)
app.include_router(tenants_routes.router)