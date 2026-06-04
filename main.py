from fastapi import FastAPI, Request, Depends, HTTPException,status
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



app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
my_secret_key = os.getenv("MY_SECRET_KEY")
app.add_middleware(SessionMiddleware, secret_key = my_secret_key)

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
  password:str


class SignupRequest(BaseModel):
  first_name : str
  last_name: str
  email:EmailStr
  password: str
  nin: str
  phone_number: str
  bvn: str


@app.on_event("startup")
def startup():
  init_db()


@app.get("/")
def index(request: Request):
    """Redirect to auth or agent based on session"""
    session = request.session
    if "user_id" in session:
        return RedirectResponse(url="/agent", status_code=302)
    return RedirectResponse(url="/auth", status_code=302)

@app.get("/auth")
def auth_page():
    """Serve authentication page"""
    with open("templates/auth.html") as f:
        return HTMLResponse(content=f.read())
        
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

@app.post("/login")
def login(details:Login,db: Session= Depends(get_db)):
  email = details.email
  password = details.password
  user = db.query(Users).filter(Users.email == email).first()
  if not user:
    raise HTTPException(
      status_code = status.HTTP_401_UNAUTHORIZED,
      detail = "Invalid password or email"
     )
  hp = PasswordHasher()
  saved_password = user.password
  verified = False
  try:
    hash_password = hp.verify(saved_password, password)
    return RedirectResponse("/agent")
  except Exception:
    verified = False
    raise HTTPException(
      status_code = status.HTTP_401_UNAUTHORIZED,
      detail = "Invalid Password or email"
    )

@app.get("/agent")
def home():
  with open("templates/index.html") as f:
    return HTMLResponse(content = f.read())

@app.post("/send-money")
def send_money(command:Command,request: Request):
  session_id = request.session.get("thread_id")
  if not session_id:
    session_id = str(uuid.uuid4())
    request.session["thread_id"]= session_id
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


user_code = {}

@app.post("/send-otp")
def send_otp(email: EmailRequest):
  msg = EmailMessage()
  secret = pyotp.random_base32()
  
  totp = pyotp.TOTP(secret,interval = 300)
  otp = totp.now()
  user_code[email.email] = {"secret":secret,"otp":otp}
  msg["Subject"] = "OTP"
  msg["From"] = EMAIL
  msg["To"] = email.email
  msg.set_content(f"Your OTP code is {otp} and expires in 5 minutes")
  try:
    with smtplib.SMTP_SSL("smtp.gmail.com",465,timeout = 15) as server:
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
