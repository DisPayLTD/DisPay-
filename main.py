from fastapi import FastAPI, Request, Depends, HTTPException,UploadFile,File,status
import json
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
from database import get_db, init_db,Users
from sqlalchemy.orm import Session
from argon2 import PasswordHasher
import pandas as pd
import io
import requests
from context import set_db_session,set_user_id




app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
my_secret_key = os.getenv("MY_SECRET_KEY")
app.add_middleware(SessionMiddleware, secret_key = my_secret_key, max_age = 600, https_only = True)

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

agent = SalaryAgentPayer(tools)

class Command(BaseModel):
    command: str
    sessionUUID: str

class EmailRequest(BaseModel):
    email: str 

class EmailOTP(BaseModel):
    email: str  
    otp: str

class Login(BaseModel):
    email: EmailStr
    password: str


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


@app.get("/")
def index(request: Request):
    """Redirect to auth or dashboard based on session"""
    session = request.session
    if "user_id" in session:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/auth", status_code=302)

@app.get("/auth")
def auth_page():
    """Serve authentication page"""
    with open("templates/auth.html") as f:
        return HTMLResponse(content=f.read())

@app.get("/dashboard")
def dashboard(request: Request):
    """Serve dashboard page - requires authentication"""
    if "user_id" not in request.session:
        return RedirectResponse(url="/auth", status_code=302)
    with open("templates/dashboard.html") as f:
        return HTMLResponse(content=f.read())


secret = os.getenv("SECRET_HASH")
@app.post("/remitron/webhook/flutterwave")
def webhook(payload:dict,req:Request,db:Session = Depends(get_db)):
	if req.headers.get("verif-hash") != secret:
		raise HTTPException(
		status_code = status.HTTP_400_UNAUTHORIZED,
		detail = "Unauthorize signature"
		)
		
	try:
		account_number = payload.get("data").get("account_number")
		user = db.query(Users).filter(Users.account_number == account_number).first()
		if not user:
			return {"status":"failed","message":"user does not exists","url":"/auth"}
		if payload.get("event") != "charge.completed":
			return{
			"status":"ignored"
			}
		amount_deposited= payload.get("data").get("amount")
		user.wallet_balance += amount_deposited
		db.commit()
		db.refresh(user)
	except Exception as e:
		return {"status":"failed","message":f"An error has occurred: {str(e)}"}

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
def signup(details: SignupRequest,db:Session = Depends(get_db)):
    ph = PasswordHasher()
    email = details.email
    password = details.password
    
    nin = details.nin
    phone_number = details.phone_number
    bvn = details.bvn
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
def login(details:Login, request: Request,db: Session= Depends(get_db)):
    email = details.email
    password = details.password
    user = db.query(Users).filter(Users.email == email).first()
    
    if not user:
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid Email"
        )
    hp = PasswordHasher()
    saved_password = user.password
    verified = False
    try:
        hash_password = hp.verify(saved_password, password)
        print("Walid this user exists and he enters his password is right ")
        session_id = request.session.get("thread_id")
        request.session["user_id"] = user.id
        set_db_session(db)
        set_user_id({"user_id":user.id,"email":email})
        if not session_id:
            session_id = str(uuid.uuid4())
            request.session["thread_id"]= session_id
			
        return {"status":"success","message":"login successfully" ,"url":"/dashboard"}
    except Exception:
        verified = False
        raise HTTPException(
            status_code = status.HTTP_401_UNAUTHORIZED,
            detail = "Invalid Password "
        )

user_code = {}

@app.post("/send-otp")
def send_otp(email: EmailRequest):
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
    print("session exists " if db_session else "session_does not exists")
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
def send_money(command:Command,request: Request,db: Session=Depends(get_db)):
    if "user_id" not in request.session:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
        }
    session_id = request.session.get("thread_id")
    if not session_id:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
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

    res = {"status":"success","ai_msg":ai_msg,"success_html_table": success_html_table,"failed_html_table": failed_html_table}
    
    print(res)
    return res
    
tx_ref = f"REMITRON-VA-{str(uuid.uuid4().hex[:16])}"

@app.get("/generate-account-number")
def generate_account_number(req: Request,db:Session = Depends(get_db)):
     
    user_id = req.session.get("user_id")
    if not user_id:
        return {
            "status":"failed",
            "message":"User not logged in",
            "url":"/auth"
        }
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {
            "status":"failed",
            "message":"User does not exist please signup or login first",
            "url":"/auth",
        }
    if user.has_wallet:
        return {
            "status":"failed",
            "message":"User already has an account number",
            "url":"/dashboard",
        }
    bvn = user.bvn
    email = user.email
    phone = user.phone_number
    first_name = user.first_name
    last_name = user.last_name
    
    api = os.getenv("FLUTTER_SECRET_API_KEY")
    header = {
        "Authorization":f"Bearer {api}" ,
        "Content-Type":"application/json"
    }
    body = {
        "email":email,
        "firstname":first_name,
        "lastname" :last_name,
        "bvn":bvn,
        "is_permanent":True,
        "phonenumber": phone,
        "tx_ref" : tx_ref,
        "narration":f"virtual account for {first_name} {last_name}"
    }
    url = "https://api.flutterwave.com/v3/virtual-account-numbers"
    try:
        res = requests.post(
            url,
            headers = header,
            json = body
        )
        res = res.json()
        account_number = res.get("data").get("account_number")
        bank_name = res.get("data").get("bank_name")
        user.account_number = account_number
        user.bank_name = bank_name
        user.has_wallet = True
        db.commit()
        db.refresh(user)
        return {
            "status":"success",
            "message":"Wallet successfully created!",
            "url":"/dashboard"
        }
    except requests.exceptions.RequestException as e:
        return {"status":"failed","message":f"An error occurred {str(e)}"}


@app.get("/transactions-history")
def transactions_history(request: Request,db: Session=Depends(get_db)):
    if not "user_id" in request.session:
        return {"status":"failed","message":"User is not logged in"}
    user_id = request.session.get("user_id")
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {"status":"failed","message":"User does not exists","url":"/auth"}
    
