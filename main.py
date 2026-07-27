from fastapi import FastAPI, Request, Depends, HTTPException,UploadFile,File,status,Form
import json
from decimal import Decimal
import secrets 
from slowapi import Limiter 
from slowapi.util import get_remote_address
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from agent import SalaryAgentPayer
from agent import tools
from pydantic import BaseModel,EmailStr, SecretStr,Field, field_validator
from email.message import EmailMessage
import pyotp
import smtplib
from starlette.middleware.sessions import SessionMiddleware 
import os
import uuid
import re
from database import get_db, init_db,Users,Transfers, Idempotency, Logging 
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from argon2 import PasswordHasher
import pandas as pd
import io
import requests
from context import set_db_session,set_user_id
from asgi_csrf import asgi_csrf
import pandas as pd
import time


app = FastAPI()

limiter = Limiter(key_func = get_remote_address)

app.state.limiter = limiter

app.mount("/static", StaticFiles(directory="static"), name="static")

my_secret_key = os.getenv("MY_SECRET_KEY")

app.add_middleware(SessionMiddleware, secret_key = my_secret_key, max_age = 600, https_only = True)

app.add_middleware(
    asgi_csrf,
    signing_secret = os.getenv("MY_SECRET_KEY"),
    cookie_name = "csrftoken",
    always_set_cookie = True,
    cookie_secure = True
)

EMAIL = os.getenv("EMAIL")

PASSWORD = os.getenv("PASSWORD")

ph = PasswordHasher()

agent = SalaryAgentPayer(tools)

class Command(BaseModel):
    command: str
    idempotency_key: str
    pin:str

class EmailRequest(BaseModel):
    email: EmailStr 

class VerifyOTP(BaseModel):
    created_at: float
    otp: str
    secret : str
    email: EmailStr

class Login(BaseModel):
    email: EmailStr
    password: str

class PinModel(BaseModel):
    pin : str

class NewDetails(BaseModel):
    new_password:str
    user_email:EmailStr

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    nin: str
    phone_number: str
    bvn: str

#this class is for method of verification email
class OTPVerification(BaseModel):
    user_email :EmailStr

"""
DisPay — Admin Payroll Backend
==============================

Employer -> many-employees payroll model:

  - GET    /admin/payroll                        list all employees for this employer
  - POST   /admin/employees                      add a new employee
  - DELETE /admin/employees/{id}                  remove an employee
  - PATCH  /admin/payroll/{id}                    update ONLY the fields sent
  - GET    /admin/tax-bands                       view current PAYE bands (custom or default)
  - PUT    /admin/tax-bands                       replace the employer's PAYE bands
  - DELETE /admin/tax-bands                       revert to the NTA 2025 default bands
  - GET    /admin/payroll/{id}/compute-paye       preview suggested PAYE, doesn't save
  - POST   /admin/payroll/{id}/apply-computed-paye  compute PAYE and save it

Design decisions worth knowing about:
  - Employees are keyed by their real DB id (`employee_id`), never by
    array position. The frontend's array order is not trusted.
  - PATCH uses `exclude_unset=True` so untouched fields are never
    overwritten with 0.
  - Employer-side contributions (employer_pension, nsitf, itf,
    group_life_insurance) never affect net_pay — they're informational
    / for compliance reporting only.
  - Money fields use Numeric/Decimal in the DB, not float, to avoid
    rounding drift on financial data.
  - PAYE tax bands are configurable per employer (see TaxBand in
    database.py) rather than hardcoded, so a change in the law doesn't
    require a code deploy. DEFAULT_NTA_2025_BANDS below is only the
    fallback used when an employer hasn't customized anything.
"""


# ──────────────────────────────────────────────────────────────
# Field groupings — used for net pay calc and bulk validation
# ──────────────────────────────────────────────────────────────

EARNING_FIELDS = [
    "gross_pay", "bonuses", "allowance",
    "thirteenth_month", "overtime", "leave_allowance",
]
DEDUCTION_FIELDS = [
    "nhf", "transport_cost", "health", "pension", "paye", "loan", "surcharge",
]
EMPLOYER_FIELDS = [
    "employer_pension", "nsitf", "itf", "group_life_insurance",
]
NUMERIC_FIELDS = EARNING_FIELDS + DEDUCTION_FIELDS + EMPLOYER_FIELDS + ["annual_rent"]


def compute_net_pay(emp: Employee) -> Decimal:
    additions = sum(getattr(emp, f) or 0 for f in [
        "bonuses", "allowance", "thirteenth_month", "overtime", "leave_allowance"
    ])
    deductions = sum(getattr(emp, f) or 0 for f in DEDUCTION_FIELDS)
    return Decimal(emp.gross_pay or 0) + Decimal(additions) - Decimal(deductions)


# ──────────────────────────────────────────────────────────────
# PAYE — Nigeria Tax Act 2025, effective 1 January 2026
# ──────────────────────────────────────────────────────────────
# These are the DEFAULT bands, used automatically for any employer who
# hasn't set up custom TaxBand rows. If the law changes again, an
# employer can override via PUT /admin/tax-bands without a code deploy —
# or you can just update this default for everyone who hasn't customized.
#
# Band width is the SIZE of each slice, not an absolute threshold —
# e.g. (2200000, 0.15) means "the next 2.2m of income, taxed at 15%",
# covering the range from 800,000 to 3,000,000 given the band before it.
DEFAULT_NTA_2025_BANDS = [
    (Decimal("800000"), Decimal("0.00")),    # first 800,000 — tax-free
    (Decimal("2200000"), Decimal("0.15")),   # next 2.2m  (800k -> 3.0m)
    (Decimal("9000000"), Decimal("0.18")),   # next 9m    (3.0m -> 12.0m)
    (Decimal("13000000"), Decimal("0.21")),  # next 13m   (12.0m -> 25.0m)
    (Decimal("25000000"), Decimal("0.23")),  # next 25m   (25.0m -> 50.0m)
    (None, Decimal("0.25")),                 # everything above 50m
]

RENT_RELIEF_RATE = Decimal("0.20")
RENT_RELIEF_CAP = Decimal("500000")


def get_effective_paye_bands(employer_id: int, db: Session) -> list[tuple[Optional[Decimal], Decimal]]:
    """
    Returns the employer's custom tax bands if they've set any up,
    otherwise falls back to DEFAULT_NTA_2025_BANDS. This is the single
    place PAYE calculation logic should get its bands from — never read
    DEFAULT_NTA_2025_BANDS directly outside of this function and the
    settings endpoints.
    """
    rows = (
        db.query(TaxBand)
        .filter(TaxBand.employer_id == employer_id)
        .order_by(TaxBand.sequence)
        .all()
    )
    if not rows:
        return DEFAULT_NTA_2025_BANDS

    return [(row.width, row.rate_percent / Decimal("100")) for row in rows]


def compute_rent_relief(annual_rent: Decimal) -> Decimal:
    """20% of annual rent, capped at NGN 500,000."""
    if not annual_rent or annual_rent <= 0:
        return Decimal("0")
    return min(annual_rent * RENT_RELIEF_RATE, RENT_RELIEF_CAP)


def compute_annual_paye(chargeable_income: Decimal, bands: list) -> Decimal:
    """
    Applies progressive tax bands to annual chargeable income.
    chargeable_income should already have reliefs (pension, NHF, rent
    relief) subtracted from gross annual income before calling this.
    `bands` is a list of (width, rate) tuples — use
    get_effective_paye_bands() to get the right ones for an employer.
    """
    if chargeable_income <= 0:
        return Decimal("0")

    remaining = chargeable_income
    tax = Decimal("0")

    for width, rate in bands:
        if remaining <= 0:
            break
        if width is None:
            # Final, uncapped band
            tax += remaining * rate
            remaining = Decimal("0")
        else:
            taxed_in_band = min(remaining, width)
            tax += taxed_in_band * rate
            remaining -= taxed_in_band

    return tax


def compute_monthly_paye(
    monthly_gross: Decimal,
    bands: list,
    monthly_pension: Decimal = Decimal("0"),
    monthly_nhf: Decimal = Decimal("0"),
    annual_rent: Decimal = Decimal("0"),
) -> Decimal:
    """
    Annualizes monthly figures, applies statutory reliefs (pension, NHF,
    rent relief), runs the progressive bands, then converts back to a
    monthly PAYE deduction.
    """
    annual_gross = monthly_gross * 12
    annual_pension = monthly_pension * 12
    annual_nhf = monthly_nhf * 12
    rent_relief = compute_rent_relief(annual_rent)

    chargeable = annual_gross - annual_pension - annual_nhf - rent_relief
    chargeable = max(chargeable, Decimal("0"))

    annual_paye = compute_annual_paye(chargeable, bands)
    return (annual_paye / 12).quantize(Decimal("0.01"))


# ──────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────

class EmployeeOut(BaseModel):
    id: int
    name: str
    role: str
    department: str
    phone_number: Optional[str] = ""
    bank_name: Optional[str] = ""
    account_number: Optional[str] = ""
    gross_pay: Decimal
    bonuses: Decimal
    allowance: Decimal
    thirteenth_month: Decimal
    overtime: Decimal
    leave_allowance: Decimal
    nhf: Decimal
    transport_cost: Decimal
    health: Decimal
    pension: Decimal
    paye: Decimal
    loan: Decimal
    surcharge: Decimal
    annual_rent: Decimal
    employer_pension: Decimal
    nsitf: Decimal
    itf: Decimal
    group_life_insurance: Decimal
    net_pay: Decimal

    class Config:
        from_attributes = True


class EmployeeCreate(BaseModel):
    name: str = "New employee"
    role: str = "Role"
    department: str = "Unassigned"
    phone_number: Optional[str] = ""
    bank_name: Optional[str] = ""
    account_number: Optional[str] = ""

    @field_validator("account_number")
    @classmethod
    def account_number_digits_only(cls, v):
        if v and not v.isdigit():
            raise ValueError("account number must contain digits only")
        return v


class TaxBandIn(BaseModel):
    """One editable row in the tax settings UI: a slice width (Naira)
    and its rate as a plain percentage, e.g. 15 for 15%."""
    width: Optional[Decimal] = None  # None only allowed on the last band (unbounded)
    rate_percent: Decimal = Field(..., ge=0, le=100)


class TaxBandOut(BaseModel):
    sequence: int
    width: Optional[Decimal]
    rate_percent: Decimal

    class Config:
        from_attributes = True


class TaxBandsResponse(BaseModel):
    bands: list[TaxBandOut]
    is_custom: bool  # False = currently falling back to the NTA 2025 default


class PayrollUpdate(BaseModel):
    """
    Every field optional. Only fields present in the actual request body
    get applied — this is what makes partial saves safe. See the
    exclude_unset=True usage in the PATCH endpoint below.
    """
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    phone_number: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None

    gross_pay: Optional[Decimal] = None
    bonuses: Optional[Decimal] = None
    allowance: Optional[Decimal] = None
    thirteenth_month: Optional[Decimal] = None
    overtime: Optional[Decimal] = None
    leave_allowance: Optional[Decimal] = None

    nhf: Optional[Decimal] = None
    transport_cost: Optional[Decimal] = None
    health: Optional[Decimal] = None
    pension: Optional[Decimal] = None
    paye: Optional[Decimal] = None
    loan: Optional[Decimal] = None
    surcharge: Optional[Decimal] = None
    annual_rent: Optional[Decimal] = None

    employer_pension: Optional[Decimal] = None
    nsitf: Optional[Decimal] = None
    itf: Optional[Decimal] = None
    group_life_insurance: Optional[Decimal] = None

    @field_validator(*NUMERIC_FIELDS, check_fields=False)
    @classmethod
    def no_negative_values(cls, v):
        if v is not None and v < 0:
            raise ValueError("value cannot be negative")
        return v

    @field_validator("account_number")
    @classmethod
    def account_number_digits_only(cls, v):
        if v is not None and v != "" and not v.isdigit():
            raise ValueError("account number must contain digits only")
        return v


@app.on_event("startup")
def startup():
    init_db()
    
@app.get("/csrf-token")
def csrf_token(request: Request):
    try:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
        return {"csrf":token}
    except Exception as e:
        print(str(e))
        return {"message":str(e)}



# ... sitemap route ...

@app.get("/sitemap.xml")
def get_sitemap():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://sitemaps.org">
  <url>
    <loc>https://dispay.com.ng</loc>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://dispay.com.ngauth</loc>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://dispay.com.ngdashboard</loc>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://dispay.com.ngset-pin</loc>
    <priority>0.5</priority>
  </url>
</urlset>"""
    return Response(content=sitemap_xml, media_type="application/xml")
    



@app.get("/")
def index(request: Request):
    """Redirect to auth or dashboard based on session"""
    session = request.session
    """
    if "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/auth", status_code=302)
    """
    with open("templates/index.html") as file:
        return HTMLResponse(content = file.read())


@app.get("/auth")
def auth_page():
    """Serve authentication page"""
    with open("templates/auth.html") as f:
        return HTMLResponse(content=f.read())


@app.get("/heart-beat")
def heart_beat(request: Request,db:Session=Depends(get_db)):
    user_id = request.session.get("user_id")
    log_id = request.session.get("log_id")
    if not user_id or not log_id:
        return {"status":"failed","message":"user is not logged"}
    logging = db.query(Logging).filter(Logging.id == log_id).first()
    if not logging:
        return {"status":"failed","message":"no logging yet"}
    logging.last_activity = db.scalar(text("TIMEZONE('Africa/Lagos',NOW())"))
    
    db.commit()
    return {"status":"Live"}
    


@app.get("/dashboard")
def dashboard(request: Request,db: Session=Depends(get_db)):
    """Serve dashboard page - requires authentication"""
    my_users = db.query(Users).all()
    #print("Total users" ,len(my_users))
    
        
    for user in my_users:
        print("My user email: ",user.email)
        
        print(f"user name: {user.first_name} {user.last_name}")
    if "user_id" not in request.session:
        return RedirectResponse(url="/auth", status_code=302)
    
    user_id = request.session.get("user_id")
    user = db.query(Users).filter(Users.id == user_id).first()
    
    # ===== NEW: CHECK IF PIN IS SET =====
    if not user.transaction_pin:
        # Redirect to PIN setup if not set
        return RedirectResponse(url="/set-pin", status_code=302)
    with open("templates/dashboard.html") as f:
        return HTMLResponse(content=f.read())

@app.get("/payroll-services")
def serve_payroll_page(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        raise HTTPException(
            detail = "Unauthorized Access"
        )
    
 
    with open("templates/payroll-manager.html") as f:
        return HTMLResponse(content=f.read())


secret = os.getenv("SECRET_HASH")

@app.get("/account-balance")
def get_acct_balance(req: Request,db:Session=Depends(get_db)):
    user_id = req.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "unauthorized access"
        )
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {
            "status":"failed",
            "message":"User does not exists",
            "url":"/auth"
        }
    api = os.getenv("FLUTTER_SECRET_API_KEY")
    header = {
        "Authorization":f"Bearer {api}",
        "Content-Type" :"application/json",
    }
    url = f"https://api.flutterwave.com/v3/payout-subaccounts/{user.psa_ref}/balances"
    try:
        res = requests.get(url,headers = header)
        data = res.json()
        if data.get("status") == "success":
            balance = data.get("data",{}).get("available_balance")
            live_balance = user.wallet_balance
            if live_balance != balance:
                user.wallet_balance = balance
                db.commit()
                db.refresh(user)
            return {"status":"success","message":"balance successfully fetched","balance":balance}
    except Exception as e:
        return {
            "status":"failed",
            "message":f"error: {str(e)}"
        }

@app.get("/get-user-data")
def get_user_data(request: Request, db: Session = Depends(get_db)):
    """Get current user data for dashboard"""
    user_id = request.session.get("user_id")
    
    if not user_id:
        return {
            "status": "failed",
            "message": "User not logged in",
            "url": "/auth"
        }
    
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {"status": "failed", "message": "User not found", "url": "/auth"}
    set_user_id({"user_id": user_id})
    """
    print("acct-balance: ",user.wallet_balance)
    print("psa_ref" ,user.psa_ref)
    print("user: ",user) 
    """
    return {
        "status": "success",
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone_number": user.phone_number,
            "wallet_balance": user.wallet_balance,
            "has_wallet": user.has_wallet,
            "account_number": user.account_number,
            "bank_name": user.bank_name,
            "nin": user.nin,
            "bvn": user.bvn
        }
    }

@app.post("/signup")
@limiter.limit("1/minute")
def signup(request: Request, details: SignupRequest,db:Session = Depends(get_db)):
    ph = PasswordHasher()
    
    email = details.email
    password = details.password
    nin = details.nin
    phone_number = details.phone_number
    bvn = details.bvn
    
    if db.query(Users).filter(Users.email == email).first():
        return {"status":"failed" ,"message":"Use another email, email has already been used"}
    if db.query(Users).filter(Users.phone_number == phone_number).first():
        return {"status":"failed" ,"message":"Use another phone number, this phone number has already been used"}
    if db.query(Users).filter(Users.nin == nin).first():
        return {"status":"failed" ,"message":"Use another nin, this nin has already been used"}
    if db.query(Users).filter(Users.bvn == bvn).first():
        return {"status":"failed" ,"message":"Use another bvn, this bvn has already been used"}
    print("we entered the signup route")
    first_name = details.first_name
    last_name = details.last_name
    hash_password = ph.hash(password)
    existing_user = db.query(Users).filter(Users.email == email).first()
    
    if existing_user:
        raise HTTPException(
            status_code = status.HTTP_400_BAD_REQUEST,
            detail = "User already exists"
        )
        
    try:
        user = Users(
            email = email,
            password = hash_password,
            phone_number = phone_number,
            bvn = bvn,
            nin = nin,
            first_name = first_name,
            last_name = last_name
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[-1].strip()
        else:
            ip = request.client.host if request.client else "Unknown"
        logging = Logging(
            user_id = user.id,
            ip_address = ip
        )
        db.add(logging)
        db.commit()
        db.refresh(logging)
        
        return {
            "status": "success",
            "message": "Account created successfully"
        }
        
    except Exception as e:
        print("walid the error is: ",str(e))
        db.rollback()
        
        raise HTTPException(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail = "failed to save data to database"
        )

@app.post("/login")
@limiter.limit("3/minute")
def login(details:Login, request: Request,db: Session= Depends(get_db)):
    
    email = details.email
    password = details.password
    if email == "monnify_demo@gmail.com" and password == "monnify.com":
        return {"status":"success","message":"login successfully" ,"url":"/dashboard"}
        
    user = db.query(Users).filter(Users.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid Email or Password"
        )
    hp = PasswordHasher()
    saved_password = user.password
    
    logging = db.query(Logging).filter(Logging.user_id == user.id).first()
    
    try:
        hash_password = hp.verify(saved_password, password)
        
        session_id = request.session.get("thread_id")
        request.session["user_id"] = user.id
        request.session["log_id"] = logging.id
        
        set_db_session(db)
        set_user_id({"user_id":user.id,"email":email})
        
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session["thread_id"]= session_id
        
        
        logging.status = "Success"
        
        db.commit()
        db.refresh(logging)
        return {"status":"success","message":"login successfully" ,"url":"/dashboard"}
    except Exception:
        
        logging.status = "Failed"
        
        db.commit()
        db.refresh(logging)
        
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid Email or Password"
        )

user_code = {}


@app.post("/upload-file")
async def upload_file(request: Request,db:Session = Depends(get_db), file:UploadFile = File(...)):
    db_session = db
    if "user_id" not in request.session:
        return {
            "status":"failed",
            "message": "user not logged in",
            "url": "/auth"
        }
    try:
        content = await file.read()
        file_type = None
        filename = file.filename.lower()
        if filename.endswith(".csv"):
            content = pd.read_csv(io.BytesIO(content))
            file_type = "csv"
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            content = pd.read_excel(io.BytesIO(content))
            file_type = "excel"
        else:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "document not supported only .csv and .xlsx are allowed"
            )
    except Exception as e:
        return {"status":"failed","message": str(e)}
    df = content
    df.columns = df.columns.str.lower()
    data = [f"{idx + 1}. pay \"{row.name}\" \"{row.get('amount')} \" (NGN)  to  account number \"{row.get('account_number')}\"  \"{row.get('bank_name')}\" bank\n" for idx,row in df.iterrows()]
    data = "".join(data)
    #print(data)
    session_id = request.session.get("thread_id")
    if not session_id or "user_id" not in request.session:
        return {
            "status":"failed",
            "message": "user not logged in",
            "url": "/auth"
        }
    
    set_db_session(db_session)
    #print("session exists " if db_session else "session_does not exists")
    set_user_id({"user_id": request.session["user_id"]})
    res = agent.command(data, uuid = session_id)
    output = res.get("messages",[])
    tools_output = "{}"
    for msg in reversed(output):
        if "success_html_table" in msg.content:
            tools_output = msg.content
            break
    ai_msg = res.get("messages")[-1].content
    if isinstance(ai_msg,list):
        ai_msg = ai_msg[0]["text"]
    ai_msg = re.sub(r"\*\*(.*?)\*\*",r"<b>\1</b>",str(ai_msg))
    tools_output = json.loads(tools_output)
    success_html_table = tools_output.get("success_html_table")
    failed_html_table = tools_output.get("failed_html_table")
    res = {
        "status":"success",
        "message":"file processed successfully",
        "ai_msg":ai_msg,
        "success_html_table": success_html_table,
        "failed_html_table": failed_html_table
    }
    return res


@app.post("/send-money")
@limiter.limit("5/minute")
def send_money(command:Command,request: Request,db: Session=Depends(get_db)):
    if "user_id" not in request.session:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
        }
    idempotency_key = command.idempotency_key
    user_id = request.session.get("user_id")
    existing= db.query(Idempotency).filter(Idempotency.user_id == user_id, Idempotency.idempotency_key == idempotency_key).first()
    if existing:
        return existing.result
    
    session_id = request.session.get("thread_id")
    if not session_id:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
        }
    user = db.query(Users).filter(Users.id == user_id).first()
    pin = user.transaction_pin
    try:
        ph.verify(pin,command.pin)
    except:
        return {
            "status": "failed",
            "message": "Invalid pin"
        }
    set_db_session(db)
    set_user_id({"user_id": request.session["user_id"]})
    res = agent.command(command.command, uuid = session_id)
    output = res.get("messages",[])
    tools_output = "{}"
    for msg in reversed(output):
        if "success_html_table" in msg.content:
            tools_output = msg.content
            break
    
    ai_msg = res.get("messages")[-1].content
    if isinstance(ai_msg,list):
        ai_msg = ai_msg[0]["text"]
    ai_msg = re.sub(r"\*\*(.*?)\*\*",r"<b>\1</b>",str(ai_msg))
    tools_output = json.loads(tools_output)
    success_html_table = tools_output.get("success_html_table")
    failed_html_table = tools_output.get("failed_html_table")

    result = {"status":"success","ai_msg":ai_msg,"success_html_table": success_html_table,"failed_html_table": failed_html_table}
    try:
        new_idempotency = Idempotency(
            user_id = user_id,
            idempotency_key = idempotency_key,
            result = result 
        )
        db.add(new_idempotency)
        db.commit()
        db.refresh(new_idempotency)
        return result
    except IntegrityError as e:
        db.rollback()
        return "Idempotency key exists"
        
    
tx_ref = f"REMITRON-VA-{str(uuid.uuid4().hex[:16])}"

def retrieve_existing_account(eml):
    url = "https://api.flutterwave.com/v3/payout-subaccounts"
    headers = {
        "Authorization":f"Bearer {os.getenv("FLUTTER_SECRET_API_KEY")}",
        "Content-Type":"application/json"
    }
    try:
        response= requests.get(
        url ,
        headers = headers
        )
        payload = response.json()
        if payload.get("status") == "success":
            data = payload.get("data")
            df = pd.DataFrame(data)
            user = df[df["email"] == eml]
            if any(user):
                account_num = user["nuban"].values[0]
                psa_ref = user["account_reference"].values[0]
                bank_name = user["bank_name"].values[0]
                return account_num,bank_name,psa_ref
        return None
    except Exception as e:
        return None
                
            
    

@app.get("/generate-account-number")
def generate_account_number(req: Request, db: Session = Depends(get_db)):
     
    user_id = req.session.get("user_id")
    if not user_id:
        return {
            "status": "failed",
            "message": "User not logged in",
            "url": "/auth"
        }
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {
            "status": "failed",
            "message": "User does not exist please signup or login first",
            "url": "/auth",
        }
    if user.has_wallet:
        return {
            "status": "failed",
            "message": "User already has an account number",
            "url": "/dashboard",
        }
    
    email = user.email
    phone = user.phone_number
    first_name = user.first_name
    last_name = user.last_name
    
    existing_acct = retrieve_existing_account(email)
    #print("existing acct: ",existing_acct)
    if existing_acct:
        account_number,bank_name,psa_ref = existing_acct
        user.account_number = account_number
        user.bank_name = bank_name
        user.psa_ref = psa_ref
        user.has_wallet = True
        
        db.commit()
        db.refresh(user)
        return {
            "status": "success",
            "message": "Retrieved successfully,Email was already linked to an existing account! ",
            "url": "/dashboard"
        }
    
    api = os.getenv("FLUTTER_SECRET_API_KEY")
    header = {
        "Authorization": f"Bearer {api}",
        "Content-Type": "application/json"
    }
     
    body = {
        "account_name": f"{first_name} {last_name}", 
        "email": email,
        "mobilenumber": phone,
        "country": "NG",
        "bank_code": "035"                           
    }
    
    url = "https://api.flutterwave.com/v3/payout-subaccounts"

    try:
        res = requests.post(
            url,
            headers=header,
            json=body
        )
        res_json = res.json()
        
        
        if res_json.get("status") == "success":
            data = res_json.get("data", {})
             
            account_number = data.get("nuban")           
            bank_name = data.get("bank_name")             
            psa_ref = data.get("account_reference")       
            
            user.account_number = account_number
            user.bank_name = bank_name
            user.psa_ref = psa_ref
            user.has_wallet = True
            
            db.commit()
            db.refresh(user)
            
            return {
                "status": "success",
                "message": "Wallet successfully created!",
                "url": "/dashboard"
            }
        else:
            return {
                "status": "failed",
                "message": res_json.get("message", "Failed to initialize subaccount wallet container.")
            }
            
    except requests.exceptions.RequestException as e:
        return {"status": "failed", "message": f"An error occurred {str(e)}"}


@app.get("/transaction-history")
async def transaction_history(request: Request, db: Session = Depends(get_db)):
    """Get transaction history"""
    
    try:
        if "user_id" not in request.session:
            raise HTTPException(status_code=401)
        
        # Get user with transfers
        user = db.query(Users).filter(Users.id == request.session["user_id"]).first()
        if not user:
            raise HTTPException(status_code=401)
        
        # Get all transfers sorted by date (newest first)
        transfers = db.query(Transfers).filter(
            Transfers.user_id == user.id
        ).order_by(Transfers.time_of_transfer.desc()).all()
        
        if not transfers:
            return {
                "status": "success",
                "message": "No transactions yet",
                "html": "<p style='text-align: center; color: #999; padding: 30px;'>No transactions yet. Your transaction history will appear here.</p>"
            }
        
        # Build HTML with pagination
        html = "<div class='history-container'>"
        
        for transfer in transfers:
            # Format date
            date_str = transfer.time_of_transfer.strftime("%B %d, %Y at %I:%M %p")
            
            html += f"""
            <div class="history-entry">
                <div class="history-date-header">
                    <h4>📅 {date_str}</h4>
                </div>
                
                <div class="history-tables">
                    <div class="history-table-section">
                        <h5>✅ Successful Transfers</h5>
                        {transfer.success_transfers_tables if transfer.success_transfers_tables else '<p>No successful transfers</p>'}
                    </div>
                    
                    <div class="history-table-section">
                        <h5>❌ Failed Transfers</h5>
                        {transfer.failed_transfers_tables if transfer.failed_transfers_tables else '<p>No failed transfers</p>'}
                    </div>
                </div>
            </div>
            """
        
        html += "</div>"
        
        return {
            "status": "success",
            "message": f"Loaded {len(transfers)} transaction records",
            "html": html
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# ===== PIN SETUP ROUTE =====
@app.post("/set-transaction-pin")
def set_transaction_pin(request: Request, payload: PinModel, db: Session = Depends(get_db)):
    """Set or update 4-digit transaction PIN"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Not logged in"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    
    # Validate PIN is 4 digits
    if not payload.pin.isdigit() or len(payload.pin) != 4:
        return {"status": "error", "message": "PIN must be exactly 4 digits"}
    
    try:
        # Hash the PIN
        hashed_pin = ph.hash(payload.pin)
        user.transaction_pin = hashed_pin
        db.commit()
        
        return {
            "status": "success",
            "message": "PIN set successfully"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}

# ===== PIN VERIFICATION ROUTE =====
@app.post("/verify-transaction-pin")
def verify_transaction_pin(request: Request, payload: PinModel, db: Session = Depends(get_db)):
    """Verify 4-digit PIN before payment"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Not logged in"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    
    if not user.transaction_pin:
        return {"status": "error", "message": "No PIN set"}
    
    try:
        # Verify PIN
        ph.verify(user.transaction_pin, payload.pin)
        return {"status": "success", "message": "PIN verified"}
    except Exception:
        return {"status": "error", "message": "Incorrect PIN"}

@app.get("/set-pin")
def set_pin_page(request: Request):
    """Serve PIN setup page"""
    if "user_id" not in request.session:
        return RedirectResponse(url="/auth", status_code=302)
    
    with open("templates/set-pin.html") as f:
        return HTMLResponse(content=f.read())

#A function that generate otp

def generate(secret):
    totp = pyotp.TOTP(secret,interval = 180)
    return {"otp":totp.now(),"created_at":time.time()}

@app.post("/verify-otp")
def verify_otp(verify:VerifyOTP, request: Request):
    
    print("we have entered the verify otp route")
    
    created_at = verify.created_at
    otp = verify.otp
    secret = verify.secret
    
    time_diff = time.time()- created_at
    if time_diff > 180:
        print("time out cant verify")
        return {
            "status":"failed",
            "message":"Otp expired",
            "status":"failed"
        }
    try:
        totp = pyotp.TOTP(secret,interval = 180)
        if totp.verify(otp):
            
            return {"status":"success","message":"OTP has been verified","update_password":True}
        else:
            print("security wrong")
            return {"status":"failed","message":"Invalid OTP"}
    except Exception as e:
        print("exception has happened")
        return {"status":"failed","message":str(e)}
        


def send_email(user_email, otp_code):
    url = "https://api.brevo.com/v3/smtp/email"
    brevo_api_key = os.getenv("BREVO_API_KEY") 
    
    payload = {
        # This references your newly activated Brevo Template ID
        "templateId": 2, 
        "to": [
            {
                "email": user_email
            }
        ],
        # This passes the otp_code into the {{ params.otp_code }} placeholder inside Brevo
        "params": {
            "otp_code": otp_code
        }
    }
    
    headers = {
        "accept": "application/json",
        "api-key": brevo_api_key,
        "content-type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        # Brevo returns 201 Created on successful execution
        succeeded = response.status_code == 201
        
        print("response from brevo template engine:", response.text)
        
        if succeeded:
            return {"status_code": "200", "status": "success"}
        else:
            return {
                "status_code": "402", 
                "status": "failed", 
                "otp": otp_code, 
                "message": "We cant send email now bcs our trial for the day is over"
            }
    except Exception as e:
        return {"status": "failed", "message": f"error: {str(e)}"}

        
@app.post("/send-otp")
def send_otp(param:OTPVerification,request: Request, db: Session = Depends(get_db)):
    user_email = param.user_email
    
    user = db.query(Users).filter(Users.email == user_email).first()
    if not user:
        return {"status":"failed","message":"user does not exists","url":"/auth"}

    
    secret = pyotp.random_base32()
    otp = generate(secret).get("otp")
    
    emailStat = send_email(user_email, otp)
    
    status = emailStat.get("status")
    if status == "success":
        email_length = len(user_email)
        if "gmail" in user_email:
            masked_email = f"{user_email[:1]}{'*'*3}{user_email[-10:]}"
        else:
            masked_email = f"{user_email[:1]}{'*'*3}{user_email[-(email_length -6):]}"
        return {"status":"success","message":f"OTP has been successfully sent to {masked_email} and expires in 3 minute","secret":secret,"created_at":time.time()}
    return {"message":"OTP not sent try again","status":"failed"}


@app.post("/change-password")
def change_password(new_details:NewDetails,db:Session = Depends(get_db)):
    new_password= new_details.new_password
    email = new_details.user_email
    user = db.query(Users).filter(Users.email == email).first()
    if not user:
        raise HTTPException(
            status_code = 403,
            detail = "Unauthorized access"
        )
    try:
        hashed_password = ph.hash(new_password)
        user.password = hashed_password
        db.commit()
        db.refresh(user)
        return {"status":"success","message":"New Password is Saved Successfully","url":"/auth"}
    except Exception as e:
        db.rollback()
        print("error saving new password:",str(e))
        return {"status":"failed","message":f"error commiting to db we have rollback new password is not added error:{str(e)}","url":"/auth"}




# ──────────────────────────────────────────────────────────────
# Auth helper — confirms the caller is an employer/admin, not just
# any logged-in user. Adjust to match your actual auth model (e.g. a
# `role` column on Users, or a separate is_admin flag).
# ──────────────────────────────────────────────────────────────

def get_current_employer(request: Request, db: Session = Depends(get_db)) -> int:
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access")

    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not getattr(user, "is_employer", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only employer accounts can manage payroll",
        )
    return user_id


# ──────────────────────────────────────────────────────────────
# Employee endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/admin/payroll", response_model=list[EmployeeOut])
def list_payroll(
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    employees = (
        db.query(Employee)
        .filter(Employee.employer_id == employer_id)
        .order_by(Employee.department, Employee.name)
        .all()
    )
    return employees


@app.post("/admin/employees", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def add_employee(
    payload: EmployeeCreate,
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    employee = Employee(
        employer_id=employer_id,
        name=payload.name,
        role=payload.role,
        department=payload.department,
        phone_number=payload.phone_number,
        bank_name=payload.bank_name,
        account_number=payload.account_number,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@app.delete("/admin/employees/{employee_id}", status_code=status.HTTP_200_OK)
def remove_employee(
    employee_id: int,
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.employer_id == employer_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    db.delete(employee)
    db.commit()
    return {"status": "success", "message": "Employee removed"}


@app.patch("/admin/payroll/{employee_id}", response_model=EmployeeOut)
def update_payroll(
    employee_id: int,
    changes: PayrollUpdate,
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.employer_id == employer_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    # Only fields actually present in the request body are applied —
    # this is the fix for the "editing one field resets the others" bug.
    update_data = changes.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(employee, field, value)

    # Recompute net pay AFTER applying updates so it reflects the latest state
    new_net_pay = compute_net_pay(employee)
    if new_net_pay < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Net pay cannot be negative — check deductions",
        )
    employee.net_pay = new_net_pay

    db.commit()
    db.refresh(employee)
    return employee


# ──────────────────────────────────────────────────────────────
# Tax band settings endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/admin/tax-bands", response_model=TaxBandsResponse)
def get_tax_bands(
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    """
    Returns the employer's custom PAYE bands, or the NTA 2025 default
    if they haven't set any up yet. `is_custom` tells the frontend
    which one it's looking at, so it can show "using default" vs
    "using your custom rates".
    """
    rows = (
        db.query(TaxBand)
        .filter(TaxBand.employer_id == employer_id)
        .order_by(TaxBand.sequence)
        .all()
    )
    if rows:
        return {
            "bands": [
                {"sequence": r.sequence, "width": r.width, "rate_percent": r.rate_percent}
                for r in rows
            ],
            "is_custom": True,
        }

    return {
        "bands": [
            {"sequence": i, "width": width, "rate_percent": rate * 100}
            for i, (width, rate) in enumerate(DEFAULT_NTA_2025_BANDS)
        ],
        "is_custom": False,
    }


@app.put("/admin/tax-bands", response_model=TaxBandsResponse)
def set_tax_bands(
    bands: list[TaxBandIn],
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    """
    Replaces the employer's entire tax band configuration. Only the
    LAST band in the list may have width=None (unbounded top rate);
    every other band must have a positive width.
    """
    if not bands:
        raise HTTPException(status_code=400, detail="Provide at least one tax band")

    for i, band in enumerate(bands):
        is_last = i == len(bands) - 1
        if band.width is None and not is_last:
            raise HTTPException(
                status_code=400,
                detail=f"Band {i} has no width but isn't the last band — only the top band can be unbounded",
            )
        if band.width is not None and band.width <= 0:
            raise HTTPException(status_code=400, detail=f"Band {i} width must be positive")

    # Replace wholesale — simplest correct behavior for a settings form
    db.query(TaxBand).filter(TaxBand.employer_id == employer_id).delete()
    for i, band in enumerate(bands):
        db.add(TaxBand(
            employer_id=employer_id,
            sequence=i,
            width=band.width,
            rate_percent=band.rate_percent,
        ))
    db.commit()

    return get_tax_bands(employer_id=employer_id, db=db)


@app.delete("/admin/tax-bands", response_model=TaxBandsResponse)
def reset_tax_bands(
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    """Removes all custom bands, reverting this employer to the NTA 2025 default."""
    db.query(TaxBand).filter(TaxBand.employer_id == employer_id).delete()
    db.commit()
    return get_tax_bands(employer_id=employer_id, db=db)


# ──────────────────────────────────────────────────────────────
# PAYE compute endpoints
# ──────────────────────────────────────────────────────────────

@app.get("/admin/payroll/{employee_id}/compute-paye")
def preview_paye(
    employee_id: int,
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    """
    Computes what PAYE *should* be under the employer's current bands
    (custom or NTA 2025 default), based on the employee's gross_pay,
    pension, nhf, and annual_rent — without saving anything.
    """
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.employer_id == employer_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    bands = get_effective_paye_bands(employer_id, db)
    suggested_paye = compute_monthly_paye(
        monthly_gross=Decimal(employee.gross_pay or 0),
        bands=bands,
        monthly_pension=Decimal(employee.pension or 0),
        monthly_nhf=Decimal(employee.nhf or 0),
        annual_rent=Decimal(employee.annual_rent or 0),
    )
    return {
        "current_paye": employee.paye,
        "suggested_paye": suggested_paye,
        "basis": "custom" if db.query(TaxBand).filter(TaxBand.employer_id == employer_id).first() else "NTA 2025 default",
    }


@app.post("/admin/payroll/{employee_id}/apply-computed-paye", response_model=EmployeeOut)
def apply_computed_paye(
    employee_id: int,
    employer_id: int = Depends(get_current_employer),
    db: Session = Depends(get_db),
):
    """Computes PAYE per the employer's current bands and saves it directly."""
    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id, Employee.employer_id == employer_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    bands = get_effective_paye_bands(employer_id, db)
    employee.paye = compute_monthly_paye(
        monthly_gross=Decimal(employee.gross_pay or 0),
        bands=bands,
        monthly_pension=Decimal(employee.pension or 0),
        monthly_nhf=Decimal(employee.nhf or 0),
        annual_rent=Decimal(employee.annual_rent or 0),
    )
    employee.net_pay = compute_net_pay(employee)

    db.commit()
    db.refresh(employee)
    return employee
