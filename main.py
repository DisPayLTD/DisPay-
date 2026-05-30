from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from agent import SalaryAgentPayer
from agent import tools
from pydantic import BaseModel
from email.message import EmailMessage
import pyotp
import smtplib
import os



app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
@app.get("/")
def home():
  with open("templates/index.html") as f:
    return HTMLResponse(content = f.read())

agent = SalaryAgentPayer(tools)

class Command(BaseModel):
    command: str 

class EmailRequest(BaseModel):
    email: str 

class EmailOTP(BaseModel):
    email: str  
    otp: str
  
@app.post("/send-money")
def send_money(command:Command):
  comm = agent.command(command.command)
  return comm


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
  msg.set_content(f"From: {msg['From']}\nContent your OTP code is {otp}")
  try:
    with smtplib.SMTP_SSL("smtp.gmail.com",465) as server:
      server.login(EMAIL,PASSWORD)
      server.send_message(msg)
      return {"status":"success","message":"sent"}
  except Exception as e:
    return {"status":"failed to send otp","message":"error","type":str(e)}
  
@app.post("/verify-otp")
def verify(user: EmailOTP):
  if not user_code.get(user.email):
    return {"Mesage":"No Secret key" }
  otp = user.otp
  totp = pyotp.TOTP(user_code.get(user.email).get("secret"),interval = 300)
  val = totp.verify(otp)
  if val:
    del user_code[user.email]
  return val
