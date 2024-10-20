from fastapi import FastAPI
from .routes import landlords_routes
from .database import Base, engine

# Cria todas as tabelas no DB
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Incluir os endpoints relacionados a expenses
app.include_router(landlords_routes.router)


@app.get("/")
def home():
    return {"message": "Expenses service for HomeHarmony"}

