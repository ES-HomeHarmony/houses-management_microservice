from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from .database import Base

class House(Base):
    __tablename__ = 'houses'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    tenants_count = Column(Integer)  # Número de inquilinos
    # landloard_id = Column(str(255)) 

    # Comentar landlord_id temporariamente
    # landlord_id = Column(Integer, ForeignKey('users.id'))
    # landlord = relationship("User")  # Relação com a tabela 'users'
