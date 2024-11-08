from sqlalchemy import Column, Integer, String, ForeignKey, Double, Date
from sqlalchemy.orm import relationship
import datetime
from app.database import Base

class House(Base):
    __tablename__ = 'houses'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    landlord_id = Column(String(255))  # Relação com a tabela 'users' id do cognito
    address = Column(String(255))
    city = Column(String(255))
    state = Column(String(255))
    zipcode = Column(String(255))

    tenents = relationship("Tenents", back_populates="house")

class Tenents(Base):
    __tablename__ = 'tenents'

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey('houses.id')) # Relação com a tabela 'houses'
    rent = Column(Double)
    tenent_id = Column(String(255))  # Relação com a tabela 'users' id do cognito

    house = relationship("House", back_populates="tenents")  # Relação com a tabela 'houses'


class Expense(Base):
    __tablename__ = 'expense'

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey('houses.id'), nullable=False)  # Relação com a tabela 'houses'
    amount = Column(Double, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(Date, default=datetime.date.today)
    deadline_date = Column(Date, nullable=True)
    file_path = Column(String(255), nullable=True)

    # Adicionar uma lista com os tenents_ids

    house = relationship("House")  # Relação com a tabela 'houses'