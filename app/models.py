from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class House(Base):
    __tablename__ = "houses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    #landlord_id = Column(Integer, ForeignKey("users.id"))  # FK para o user (landlord)
    tenants_count = Column(Integer)  # Número de inquilinos

    #landlord = relationship("User")  # Associação com o microserviço de Users
