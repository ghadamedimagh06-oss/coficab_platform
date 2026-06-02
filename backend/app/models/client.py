from sqlalchemy import Column, Integer, String, Numeric, DateTime, Time, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)  # client_id business code
    nom = Column(Text, nullable=False)
    address = Column(Text)
    city = Column(Text)
    country = Column(Text)
    email = Column(String(100))
    numero = Column(String(30))
    latitude = Column(Numeric(9, 6))
    longitude = Column(Numeric(9, 6))
    fenetre_ouverture = Column(Time)
    fenetre_fermeture = Column(Time)
    exigences = Column(Text)
    date_creation = Column(DateTime(timezone=True), server_default=func.now())

    demandes = relationship("DemandeLocal", back_populates="client")
