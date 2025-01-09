from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os
import logging

env = os.getenv('ENV', 'development')
env_file = f'.env/{env}.env'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("house_service_db")

# Load environment variables from file
if os.path.exists(env_file):
    load_dotenv(env_file)

# Retrieve credentials from environment variables
db_user = os.getenv('DB_USER')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_name = os.getenv('DB_NAME')
db_port = os.getenv('DB_PORT')

DATABASE_URL = f'mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'

logger.info(f'URL_DATABASE CONNECTED')


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency para obter sessão da DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
