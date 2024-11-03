from sqlalchemy import Column, Integer, String, ForeignKey, Double, Date
from sqlalchemy.orm import relationship
import datetime
from app.database import Base

class House(Base):
    __tablename__ = 'houses'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    landlord_id = Column(String(255))  # Relation with the 'users' table (Cognito ID)
    address = Column(String(255))
    city = Column(String(255))
    state = Column(String(255))
    zipcode = Column(String(255))

    tenents = relationship("Tenents", back_populates="house")


class Tenents(Base):
    __tablename__ = 'tenents'

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey('houses.id'))  # Relation with the 'houses' table
    rent = Column(Double)
    tenent_id = Column(String(255))  # Relation with the 'users' table (Cognito ID)

    house = relationship("House", back_populates="tenents")
    expenses = relationship("TenantExpense", back_populates="tenant")


class Expense(Base):
    __tablename__ = 'expense'

    id = Column(Integer, primary_key=True, index=True)
    house_id = Column(Integer, ForeignKey('houses.id'), nullable=False)  # Relation with the 'houses' table
    amount = Column(Double, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(Date, default=datetime.date.today)
    deadline_date = Column(Date, nullable=True)
    file_path = Column(String(255), nullable=True)

    house = relationship("House")
    tenants = relationship("TenantExpense", back_populates="expense")


class TenantExpense(Base):
    __tablename__ = 'tenant_expense'

    tenant_id = Column(Integer, ForeignKey('tenents.id'), primary_key=True)
    expense_id = Column(Integer, ForeignKey('expense.id'), primary_key=True)
    status = Column(String(255), default='pending')  # Status of the tenant's portion of the expense

    tenant = relationship("Tenents", back_populates="expenses")
    expense = relationship("Expense", back_populates="tenants")
