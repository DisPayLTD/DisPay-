import os
from sqlalchemy import String, Float, create_engine, Column, Integer, DateTime, func, ForeignKey, Numeric,Text, JSON,text, Boolean
from sqlalchemy.orm import sessionmaker
from typing import Any
from sqlalchemy.orm import declarative_base, relationship,Mapped,mapped_column


SQL_URL = os.getenv("DATABASE_URL", "sqlite:///./remitron.db")

Base = declarative_base()

class Users(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, default="Unknown")
    last_name = Column(String, default="Unknown")
    email = Column(String(255), unique = True)
    password = Column(String)
    psa_ref = Column(String, unique=True)
    dob = Column(Date, nullable=True)
    gender = Column(String, nullable=True)
    address = Column(String, nullable=True)
    nin = Column(String, unique = True)
    phone_number = Column(String, unique=True)
    bvn = Column(String, unique=True)
    has_wallet = Column(Boolean, default=False)
    account_number = Column(String)
    bank_name = Column(String)
    transaction_pin = Column(String)
    transactions:Mapped[list[dict[str,Any]]] = mapped_column(JSON,nullable = True, default=list)
    wallet_balance = Column(Float, default=0.0)
    creation_time = Column(DateTime(timezone=True), server_default=func.now())
    transfers = relationship("Transfers", back_populates="user")
    is_employer = Column(Integer, default=0,nullable=True)


class Employee(Base):
    __tablename__ = "employee"

    # Core Identification
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    state_of_residence = Column(String(255),nullable=False)
    
    #employer_id = Column(Integer, ForeignKey("employers.id"))
    #employer = relationship("Organization",back_populates="employees")

    # Financial Base Components
    monthly_basic = Column(Numeric(15, 2), nullable=False)
    monthly_housing = Column(Numeric(15, 2), nullable=False)
    monthly_transport = Column(Numeric(15, 2), nullable=False)
    bvn = Column(String(11), nullable=True)
    nin = Column(String(11), nullable=False)

    # Pension Configuration
    pension_pfa_name = Column(String(150), nullable=False)
    pension_pin = Column(String(50), nullable=False)
    employee_pension_rate = Column(Numeric(5, 6), nullable=True,default=0.006667)
    
    #health assurance
    monthly_life_assurance = Column(Numeric(5, 6), nullable=True,default=0.00)
    
    #Additional Pay 
    allowance = Column(Numeric(15, 2), nullable=True)
    bonus = Column(Numeric(15, 2), nullable=True)
    
    #expenses
    loans = Column(Numeric(15, 2), nullable=True,default=0.00)
    unpaid_loan = Column(Numeric(15,2),nullable=True,default=0.00)
    surcharge = Column(Numeric(15,2),nullable=True,default=0.00)
    


    # Housing Fund
    opt_in_nhf = Column(Boolean, nullable=False, default=False)
    nhf_number = Column(String(50), nullable=True)
    nhf_rate = Column(Numeric(5, 4), nullable=True,default=0.025)

    # Bank Details
    bank_name = Column(String(100), nullable=False)
    bank_code = Column(String(20), nullable=False)
    account_number = Column(String(10), nullable=False)

class Transfers(Base):
    
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True, unique=True)
    time_of_transfer = Column(DateTime(timezone=True),server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))
    success_transfers_tables = Column(Text)
    failed_transfers_tables = Column(Text)
    status = Column(String)
    user = relationship("Users", back_populates="transfers")


class Idempotency(Base):
    __tablename__ = "idempotency"
    id = Column(Integer,primary_key = True)
    user_id = Column(Integer,ForeignKey("users.id"))
    idempotency_key= Column(String, unique=True)
    result = Column(JSON)
    created_at = Column(DateTime(timezone=True),server_default = func.now())


class Logging(Base):
    __tablename__ = "logging"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    
    #Postgres to take the current timestamp and transform it to West Africa Time (+1)
    login_time = Column(
        DateTime, 
        server_default=text("TIMEZONE('Africa/Lagos', NOW())")
    )
    
    logout_time = Column(DateTime, nullable=True)
    duration = Column(String, nullable=True)
    login_attempts = Column(Integer, default=1)
    status = Column(String, default="success")  
    ip_address = Column(String, nullable=True)


engine = create_engine(SQL_URL)
sessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    #Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
