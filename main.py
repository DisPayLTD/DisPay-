from fastapi import FastAPI, Request, Depends, HTTPException,UploadFile,File,status,Form,Header
import hmac
import hashlib
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import json
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
from database import get_db, init_db,Users,Transfers, Idempotency, Logging , engine 
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
from typing import Optional
from datetime import date
from fastapi.responses import Response

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
    dob: date
    gender: str
    is_employer : bool
    address: str

class OTPVerification(BaseModel):
    user_email :EmailStr

class EmployeePayrollRequest(BaseModel):
    """
    Validates a complete, flat JSON payload for Nigerian payroll creation.
    Pass this directly as the request body data type in your API route.
    """
    employee_id: str 
    first_name: str 
    last_name: str 
    email: str 
    state_of_residence: str
    
    monthly_basic: Decimal 
    monthly_housing: Decimal
    monthly_transport: Decimal
    bvn: str 
    nin: str 
    
    pension_pfa_name: str
    pension_pin: str 
    employee_pension_rate: Decimal 
    
    monthly_life_assurance:Optional[Decimal]
    
    allowance: Optional[Decimal]
    bonus: Optional[Decimal]
    
    loans:Optional[Decimal]
    unpaid_loan : Optional[Decimal]
    surcharge: Optional[Decimal]
    
    opt_in_nhf: bool 
    nhf_number: Optional[str]
    nhf_rate:Optional[Decimal]
    
    bank_name: str 
    bank_code: str 
    account_number: str 

    @field_validator("bvn", "nin", "account_number")
    @classmethod
    def validate_numeric_strings(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Value must contain numeric characters only.")
        return v

class BuyAirtimeRequest(BaseModel):
    network: str
    phone_number: str
    amount: float

class BuyDataRequest(BaseModel):
    network: str
    phone_number: str
    data_plan: str

class BuyElectricityRequest(BaseModel):
    disco: str
    meter_type: str
    meter_number: str
    amount: float

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
    
    for user in my_users:
        print("My user email: ",user.email)
        print(f"user name: {user.first_name} {user.last_name}")
    if "user_id" not in request.session:
        return RedirectResponse(url="/auth", status_code=302)
    
    user_id = request.session.get("user_id")
    user = db.query(Users).filter(Users.id == user_id).first()
    
    if not user.transaction_pin:
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
    if email == "walidsagir8@gmail.com":
        delete_user_by_email(email,db)
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
    is_employer = details.is_employer
    dob = details.dob
    gender = details.gender
    address = details.address
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
            last_name = last_name,
            is_employer = is_employer,
            dob = dob,
            gender = gender,
            address = address 
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

@app.post("/logout")
def logout(request: Request):
    """Clear session and logout user"""
    request.session.clear()
    return {"status": "success", "message": "Logged out successfully"}

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
    session_id = request.session.get("thread_id")
    if not session_id or "user_id" not in request.session:
        return {
            "status":"failed",
            "message": "user not logged in",
            "url": "/auth"
        }
    
    set_db_session(db_session)
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




logger = logging.getLogger("squad_webhook")

SQUAD_SECRET_KEY = os.getenv("SQUAD_API_KEY")


@app.post("/webhooks/squad")  # `app` = your existing FastAPI() instance in main.py
def squad_webhook_listener(
    request: Request,
    x_squad_encrypted_body: str = Header(None),
    db: Session = Depends(get_db),
):
    # 1. Require the signature header
    if not x_squad_encrypted_body:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing signature header.",
        )

    # 2. Raw bytes of the request body (sync version doesn't need `await`)
    raw_payload_bytes = request.body()  # NOTE: see warning below about this line

    # 3. Compute HMAC SHA512
    computed_hash = hmac.new(
        key=SQUAD_SECRET_KEY.encode("utf-8"),
        msg=raw_payload_bytes,
        digestmod=hashlib.sha512,
    ).hexdigest().upper()

    # 4. Constant-time compare
    if not hmac.compare_digest(computed_hash, x_squad_encrypted_body.upper()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature verification failed.",
        )

    # 5. Parse the payload
    payload: Dict[str, Any] = request.json()  # NOTE: see warning below too

    channel = payload.get("channel")
    transaction_indicator = payload.get("transaction_indicator")
    tx_reference = payload.get("transaction_reference")
    customer_identifier = payload.get("customer_identifier")
    settled_amount_raw = payload.get("settled_amount")
    sender_name = payload.get("sender_name")

    if channel != "virtual-account" or transaction_indicator != "C":
        return {"status": "ignored", "reason": "Not a virtual account credit event."}

    if not customer_identifier or not tx_reference:
        logger.error("Squad webhook missing identifiers: %s", payload)
        return {"status": "ignored", "reason": "Missing required identifiers."}

    try:
        settled_amount = Decimal(settled_amount_raw)
    except (InvalidOperation, TypeError):
        logger.error("Squad webhook invalid settled_amount: %s", payload)
        return {"status": "ignored", "reason": "Invalid amount format."}

    # --- Look up user with sync db.query() ---
    user = db.query(User).filter(User.psa_ref == customer_identifier).first()

    if user is None:
        logger.error(
            "Squad webhook: no user found for psa_ref=%s (tx_ref=%s)",
            customer_identifier, tx_reference,
        )
        return {"status": "ignored", "reason": "Unknown customer_identifier."}

    # --- Idempotency check ---
    existing_refs = {
        tx.get("transaction_reference")
        for tx in (user.transactions or [])
    }
    if tx_reference in existing_refs:
        return {"status": "success", "message": "Transaction already recorded."}

    # --- Credit balance ---
    user.wallet_balance = float(Decimal(str(user.wallet_balance)) + settled_amount)

    new_tx_record = {
        "transaction_reference": tx_reference,
        "amount": str(settled_amount),
        "sender_name": sender_name,
        "channel": channel,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    """
    if user.transactions is None:
        user.transactions = [new_tx_record]
    else:
        user.transactions.append(new_tx_record)
        flag_modified(user, "transactions")
    """

    db.commit()

    logger.info(
        "Credited user %s with %s NGN (tx_ref=%s, new_balance=%s)",
        user.id, settled_amount, tx_reference, user.wallet_balance,
    )

    return {"status": "success"}
        
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
        
tx_ref = f"DISPAY-VA-{str(uuid.uuid4().hex[:16])}"

def retrieve_existing_account(eml):
    url = "https://api.flutterwave.com/v3/payout-subaccounts"
    headers = {
        "Authorization": f"Bearer {os.getenv('FLUTTER_SECRET_API_KEY')}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
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
    tx_ref = f"DISPAY-VA-{str(uuid.uuid4().hex[:16])}"
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
    dob = user.dob
    dob = dob.strftime("%m/%d/%Y")
    gender = user.gender
    
    if gender== "male":
        gender = "1"
    else:
        gender = "2"
    bvn = user.bvn
    address = user.address
    
    api = os.getenv("KORA_API_KEY")
    header = {
        "Authorization": f"Bearer {api}",
        "Content-Type": "application/json"
    }
     
    
    url = "https://api.korapay.com/merchant/api/v1/virtual-bank-account"
    
    payload = {
        "account_name": f"{first_name} {last_name}",
        "account_reference": tx_ref,
        "permanent": True,
        "bank_code": "090405",
        "customer": {
            "email": email,
            "name": f"{first_name} {last_name}"
        },
        "kyc": {
            "bvn": bvn
        }
    }
    try:
        res = requests.post(url, headers=header, json=body)
        res_json = res.json()
        print("res_json: ",res_json)
              
        if res_json.get("status"):
            data = res_json.get("data", {})
            
            print("generate account number",data)
            
            param = res_json.get("data", {})
            bank_name = param.get("bank_name")
            account_number = param.get("account_number")
            created_at = param.get("created_at")
            unique_id = param.get("unique_id")       
            
            user.account_number = account_number
            user.bank_name = bank_name
            user.psa_ref = unique_id
            user.creation_time = created_at
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
        
        user = db.query(Users).filter(Users.id == request.session["user_id"]).first()
        if not user:
            raise HTTPException(status_code=401)
        
        transfers = db.query(Transfers).filter(
            Transfers.user_id == user.id
        ).order_by(Transfers.time_of_transfer.desc()).all()
        
        if not transfers:
            return {
                "status": "success",
                "message": "No transactions yet",
                "html": "<p style='text-align: center; color: #999; padding: 30px;'>No transactions yet. Your transaction history will appear here.</p>"
            }
        
        html = "<div class='history-container'>"
        
        for transfer in transfers:
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

@app.post("/set-transaction-pin")
def set_transaction_pin(request: Request, payload: PinModel, db: Session = Depends(get_db)):
    """Set or update 4-digit transaction PIN"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Not logged in"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    
    if not payload.pin.isdigit() or len(payload.pin) != 4:
        return {"status": "error", "message": "PIN must be exactly 4 digits"}
    
    try:
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
        "templateId": 2, 
        "to": [
            {
                "email": user_email
            }
        ],
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

# ===== NEW: AIRTIME, DATA, ELECTRICITY ROUTES =====

@app.post("/buy-airtime")
@limiter.limit("10/minute")
def buy_airtime(request: Request, payload: BuyAirtimeRequest, db: Session = Depends(get_db)):
    """Buy airtime from Squad API"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "failed", "message": "Not logged in", "url": "/auth"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {"status": "failed", "message": "User not found", "url": "/auth"}
    
    if user.wallet_balance < payload.amount:
        return {"status": "failed", "message": "Insufficient balance"}
    
    api_key = os.getenv("SQUAD_API_KEY")
    url = "https://api-d.squadco.com/airtime/topup"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "phone_number": payload.phone_number,
        "network": payload.network,
        "amount": payload.amount
    }
    
    try:
        res = requests.post(url, headers=headers, json=body)
        response_data = res.json()
        
        if response_data.get("success"):
            user.wallet_balance -= payload.amount
            db.commit()
            db.refresh(user)
            
            return {
                "status": "success",
                "message": f"Airtime purchased successfully! {payload.network} - {payload.phone_number} - ₦{payload.amount}"
            }
        else:
            return {
                "status": "failed",
                "message": response_data.get("message", "Failed to purchase airtime")
            }
    except Exception as e:
        return {"status": "failed", "message": f"Error: {str(e)}"}

@app.post("/buy-data")
@limiter.limit("10/minute")
def buy_data(request: Request, payload: BuyDataRequest, db: Session = Depends(get_db)):
    """Buy data from Squad API"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "failed", "message": "Not logged in", "url": "/auth"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {"status": "failed", "message": "User not found", "url": "/auth"}
    
    data_plans = {
        "500MB": {"price": 200, "sku": "500M"},
        "1GB": {"price": 300, "sku": "1G"},
        "2GB": {"price": 500, "sku": "2G"},
        "3GB": {"price": 800, "sku": "3G"},
        "5GB": {"price": 1200, "sku": "5G"},
        "10GB": {"price": 2500, "sku": "10G"}
    }
    
    plan_info = data_plans.get(payload.data_plan)
    if not plan_info:
        return {"status": "failed", "message": "Invalid data plan"}
    
    if user.wallet_balance < plan_info["price"]:
        return {"status": "failed", "message": "Insufficient balance"}
    
    api_key = os.getenv("SQUAD_API_KEY")
    url = "https://api-d.squadco.com/data/topup"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "phone_number": payload.phone_number,
        "network": payload.network,
        "sku": plan_info["sku"]
    }
    
    try:
        res = requests.post(url, headers=headers, json=body)
        response_data = res.json()
        
        if response_data.get("success"):
            user.wallet_balance -= plan_info["price"]
            db.commit()
            db.refresh(user)
            
            return {
                "status": "success",
                "message": f"Data purchased successfully! {payload.network} - {payload.phone_number} - {payload.data_plan}"
            }
        else:
            return {
                "status": "failed",
                "message": response_data.get("message", "Failed to purchase data")
            }
    except Exception as e:
        return {"status": "failed", "message": f"Error: {str(e)}"}

@app.post("/buy-electricity")
@limiter.limit("10/minute")
def buy_electricity(request: Request, payload: BuyElectricityRequest, db: Session = Depends(get_db)):
    """Pay electricity bill from Squad API"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "failed", "message": "Not logged in", "url": "/auth"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {"status": "failed", "message": "User not found", "url": "/auth"}
    
    if user.wallet_balance < payload.amount:
        return {"status": "failed", "message": "Insufficient balance"}
    
    api_key = os.getenv("SQUAD_API_KEY")
    url = "https://api-d.squadco.com/electricity/pay"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    body = {
        "disco": payload.disco,
        "meter_type": payload.meter_type,
        "meter_number": payload.meter_number,
        "amount": payload.amount
    }
    
    try:
        res = requests.post(url, headers=headers, json=body)
        response_data = res.json()
        
        if response_data.get("success"):
            user.wallet_balance -= payload.amount
            db.commit()
            db.refresh(user)
            
            return {
                "status": "success",
                "message": f"Electricity bill paid successfully! {payload.disco} - {payload.meter_number} - ₦{payload.amount}"
            }
        else:
            return {
                "status": "failed",
                "message": response_data.get("message", "Failed to pay electricity bill")
            }
    except Exception as e:
        return {"status": "failed", "message": f"Error: {str(e)}"}

def delete_user_by_email(email: str, db: Session) -> dict:
    user = db.query(Users).filter(Users.email == email).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    """

    if user.wallet_balance and user.wallet_balance > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete user with a non-zero wallet balance (₦{user.wallet_balance}). "
                   f"Settle or transfer funds first.",
        )
    """

    db.delete(user)
    db.commit()

    return {"status": "success", "message": f"User with email {email} deleted."}
