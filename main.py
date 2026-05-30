From fastapi import FastAPI
from fastapi.responses import HTMLResponse
from agent import SalaryAgentPayer
from agent import tools
from pydantic import BaseModel
from email.message import EmailMessage
import pyotp
import smtplib
import os


app = FastAPI()


EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
@app.get("/")
def home():
  with open("templates/index.html") as f:
    return HTMLResponse(content = f.read())

agent = SalaryAgentPayer(tools)

class Command(BaseModel):
  command:str
  otp:str
  
@app.post("/send_money")
def send_money(command:Command):
  comm = agent.command(command.command)
  return comm


user_code = {}

@app.post("/send_otp")
def send_otp():
  msg = EmailMessage()
  secret = pyotp.random_base32()
  user_code["secret"] = secret
  totp = pyotp.TOTP(secret,interval = 300)
  otp = totp.now()
  msg["Subject"] = "OTP"
  msg["From"] = EMAIL
  msg["To"] = "walidsagir27@gmail.com"
  msg.set_content(f"From: {msg['From']}\nContent your OTP code is {otp}")
  try:
    with smtplib.SMTP_SSL("smtp.gmail.com",465) as server:
      server.login(EMAIL,PASSWORD)
      server.send_message(msg)
      return {"Message":"sent"}
  except Exception as e:
    return {"Message":"error","type":str(e)}
  
  return otp
  
@app.post("/verify_otp")
def verify(comm:Command):
  if not user_code.get("secret"):
    return {"Mesage":"No Secret key" }
  otp = comm.otp
  totp = pyotp.TOTP(user_code.get("secret"),interval = 300)
  val = totp.verify(otp)
  if val:
    del user_code["secret"]
  return val
