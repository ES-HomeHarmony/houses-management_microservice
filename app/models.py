from sqlalchemy import Column, Integer, String, ForeignKey, Double
from sqlalchemy.orm import relationship
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

    # tenents = relationship("Tenents", back_populates="house")  # Relação com a tabela 'tenents'

    # Comentar landlord_id temporariamente
    # landlord_id = Column(Integer, ForeignKey('users.id'))
    # landlord = relationship("User")  # Relação com a tabela 'users'

# class Tenents(Base):
#     __tablename__ = 'tenents'

#     id = Column(Integer, primary_key=True, index=True)
#     house_id = Column(Integer, ForeignKey('houses.id')) # Relação com a tabela 'houses'
#     rent = Column(Double)
#     tenent_id = Column(String(255))  # Relação com a tabela 'users' id do cognito

#     house = relationship("House", back_populates="tenents")  # Relação com a tabela 'houses'

