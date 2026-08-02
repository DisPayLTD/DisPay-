import os
from sqlalchemy import String, Float, Date,create_engine, Column, Integer, DateTime, func, ForeignKey, Numeric,Text, JSON,text, Boolean
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
    transfers = relationship("Transfers", back_populates="user", cascade="all, delete-orphan")
    is_employer = Column(Integer, default=0,nullable=True)
    idempotency = relationship("Idempotency",back_populates = "user",cascade ="all, delete-orphan")


class Employee(Base):
    __tablename__ = "employee"

    # Core Identification
    id = Column(Integer, primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    state_of_residence = Column(String(255),nullable=False)
    
    employer_id = Column(Integer, ForeignKey("organization.id"))
    employer = relationship("Organization",back_populates="employees")

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



class Organization(Base):
    __tablename__ = "organization"

    id = Column(Integer, primary_key=True, unique=True)

    # --- Business identity / registration ---
    cac = Column(String, nullable=True)
    tin = Column(String, nullable=True)
    director = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    registration_type = Column(String, nullable=True)  # e.g. "Business Name" vs "Limited Liability"

    # --- Contact ---
    email = Column(String(255), unique=True, nullable=True)
    phone_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    state = Column(String, nullable=True)  # determines applicable State IRS for PAYE remittance


    # --- Virtual account fields ---
    account_name = Column(String, nullable=True)
    account_number = Column(String, nullable=True)
    bank_name = Column(String, nullable=True)
    bank_code = Column(String, nullable=True)
    account_reference = Column(String, unique=True, nullable=True)
    unique_id = Column(String, nullable=True)
    has_wallet = Column(Boolean, default=False)
    account_balance = Column(Numeric(14, 2), nullable=True, default=0)

    # --- Payroll contribution rates/amounts ---
    pension_contribution = Column(Numeric(14, 2), nullable=True)
    nhf_contribution = Column(Numeric(14, 2), nullable=True)
    health_insurance_contribution = Column(Numeric(14, 2), nullable=True)

    # --- Statutory / compliance identifiers ---
    pencom_employer_code = Column(String, nullable=True)  # PenCom/RSA employer registration
    nsitf_number = Column(String, nullable=True)           # Nigeria Social Insurance Trust Fund
    itf_number = Column(String, nullable=True)             # Industrial Training Fund
    kyb_status = Column(String, nullable=True)              # "pending", "verified", "rejected"
    remita_agency_code = Column(String, nullable=True)      # NOTA/Remita integration reference

    # --- Payroll operational fields ---
    payroll_frequency = Column(String, nullable=True)  # "monthly", "biweekly", "weekly"
    pay_day = Column(Integer, nullable=True)             # e.g. 25th of each month
    last_payroll_run_at = Column(DateTime(timezone=True), nullable=True)
    next_payroll_run_at = Column(DateTime(timezone=True), nullable=True)

    # --- Ownership / access control ---
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # --- Status / lifecycle ---
    is_active = Column(Boolean, default=True)

    # --- Branding ---
    logo_url = Column(String, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # --- Relationships ---
    employees = relationship(
        "Employee",
        back_populates="employer",
        foreign_keys="Employee.employer_id",
        cascade="all, delete-orphan",
    )

    # The specific User who owns/administers this organization's account
    owner = relationship("Users", foreign_keys=[owner_user_id])


class Transfers(Base):
    
    __tablename__ = "transfers"
    id = Column(Integer, primary_key=True, unique=True)
    time_of_transfer = Column(DateTime(timezone=True),server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"))
    success_transfers_tables = Column(Text)
    failed_transfers_tables = Column(Text)
    status = Column(String)
    user = relationship("Users", back_populates="transfers")


class FrequencyPayment(Base):
    __tablename__ = "frequency_payment"
    id = Column(Integer, primary_key=True)
    # --- schedule payments (electricity, data, airtime e.t.c) ---

    #--- Payment name ---
    payment_name = Column(String,nullable = True)

    #--- Data required for frequency payment---
    meter_name = Column(String,nullable = True)
    disco = Column(String,nullable = True)
    phone_number = Column(String,nullable=True)

    #--- payment type ---
    airtime = Column(Boolean,nullable =True)
    data = Column(Boolean,nullable = True)
    electricity = Column(Boolean,nullable=True)

    #--- frequency of payment---
    frequency_data = Column(String,nullable=True)
    frequency_electricity = Column(String,nullable=True)
    frequency_airtime = Column(String,nullable=True)

    #--- payment amounts ---
    airtime_payment_amount = Column(Numeric(11,5),nullable = True)
    data_payment_amount = Column(Numeric(11,5),nullable = True)
    electricity_payment_amount = Column(Numeric(11,5),nullable = True)
    
    
    

class Idempotency(Base):
    __tablename__ = "idempotency"
    id = Column(Integer,primary_key = True)
    user_id = Column(Integer,ForeignKey("users.id"))
    idempotency_key= Column(String, unique=True)
    result = Column(JSON)
    user = relationship("Users",back_populates="idempotency")
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
    
