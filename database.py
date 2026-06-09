import os
from sqlalchemy import String, Float, create_engine, Column, Integer, DateTime, func, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base, relationship 

SQL_URL = os.getenv("DATABASE_URL", "sqlite:///./remitron.db")

Base = declarative_base()

class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, default="Unknown")
    last_name = Column(String, default="Unknown")
    email = Column(String(255), unique = True)
    password = Column(String)
    nin = Column(String, unique = True)
    phone_number = Column(String, unique=True)
    bvn = Column(String, unique=True)
    has_wallet = Column(Boolean, default=False)
    account_number = Column(String)
    bank_name = Column(String)
    transactions = Column(JSON)
    wallet_balance = Column(Float, default=0.0)
    creation_time = Column(DateTime(timezone=True), server_default=func.now())
    transfers = relationship("Transfers", back_populates="user")
    
class Transfers(Base):
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True, unique=True)
    time_of_transfer = Column(DateTime(timezone=True),server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))
    sucess_transfers_tables = Column(Text)
    failed_transfers_tables = Column(Text)
    user = relationship("Users", back_populates="transfers")

engine = create_engine(SQL_URL)
sessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
