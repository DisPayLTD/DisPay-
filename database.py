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


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employer_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    name = Column(String, nullable=False, default="New employee")
    role = Column(String, nullable=False, default="Role")
    department = Column(String, nullable=False, default="Unassigned")

    # Contact & bank details — stored as strings deliberately. Account
    # numbers can have leading zeros, and neither field is ever used
    # in arithmetic, so Numeric/Integer would be the wrong type here.
    phone_number = Column(String, nullable=True, default="")
    bank_name = Column(String, nullable=True, default="")
    account_number = Column(String, nullable=True, default="")

    # Earnings
    gross_pay = Column(Numeric(12, 2), nullable=False, default=0)
    bonuses = Column(Numeric(12, 2), nullable=False, default=0)
    allowance = Column(Numeric(12, 2), nullable=False, default=0)
    thirteenth_month = Column(Numeric(12, 2), nullable=False, default=0)
    overtime = Column(Numeric(12, 2), nullable=False, default=0)
    leave_allowance = Column(Numeric(12, 2), nullable=False, default=0)

    # Employee-side deductions
    nhf = Column(Numeric(12, 2), nullable=False, default=0)
    transport_cost = Column(Numeric(12, 2), nullable=False, default=0)
    health = Column(Numeric(12, 2), nullable=False, default=0)
    pension = Column(Numeric(12, 2), nullable=False, default=0)  # employee share; 0 = employer covers 100%
    paye = Column(Numeric(12, 2), nullable=False, default=0)
    loan = Column(Numeric(12, 2), nullable=False, default=0)
    surcharge = Column(Numeric(12, 2), nullable=False, default=0)

    # Employer-side contributions — never subtracted from net pay
    employer_pension = Column(Numeric(12, 2), nullable=False, default=0)
    nsitf = Column(Numeric(12, 2), nullable=False, default=0)
    itf = Column(Numeric(12, 2), nullable=False, default=0)
    group_life_insurance = Column(Numeric(12, 2), nullable=False, default=0)

    net_pay = Column(Numeric(12, 2), nullable=False, default=0)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


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
    
