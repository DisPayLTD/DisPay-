from fastapi import FastAPI, Request, Depends, HTTPException,UploadFile,File,status,Form
import json
import secrets 
from slowapi import Limiter 
from slowapi.util import get_remote_address
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from agent import SalaryAgentPayer
from agent import tools
from pydantic import BaseModel,EmailStr
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
    email: str 

class EmailOTP(BaseModel):
    email: str  
    otp: str

class Login(BaseModel):
    email: EmailStr
    password: str

class PinModel(BaseModel):
    pin : str


class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    nin: str
    phone_number: str
    bvn: str


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
    print("Total users" ,len(my_users))
    
        
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
    print("acct-balance: ",user.wallet_balance)
    print("psa_ref" ,user.psa_ref)
    print("user: ",user)  
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

@app.post("/send-otp")
@limiter.limit("5/hour")
def send_otp(request: Request,email: EmailRequest):
    msg = EmailMessage()
    secret = pyotp.random_base32()
    
    totp = pyotp.TOTP(secret,interval = 300)
    otp = totp.now()
    print('ur otp is: ',otp)
    user_code[email.email] = {"secret":secret,"otp":otp}
    msg["Subject"] = "OTP"
    msg["From"] = EMAIL
    msg["To"] = email.email
    msg.set_content(f"Your OTP code is {otp} and expires in 5 minutes")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,timeout = 5) as server:
            server.login(EMAIL,PASSWORD)
            server.send_message(msg)
            return {"status":"success","message":"sent"}
    except Exception as e:
        if otp:
            return {"status":"success","message":f"walid your culprit {str(e)}","otp":str(otp)}
    
@app.post("/verify-otp")
def verify(user: EmailOTP):
    if not user_code.get(user.email):
        return {"Mesage":"No Secret key" }
    otp = user.otp
    totp = pyotp.TOTP(user_code.get(user.email).get("secret"),interval = 300)
    val = totp.verify(otp)
    if val:
        del user_code[user.email]
    return {"authenticated":val}

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
    print(data)
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
