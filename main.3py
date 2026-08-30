from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os
from pydantic import BaseModel
import requests


class VerifyAccountDetails(BaseModel):
    account_number: str
    bank_code: str


app = FastAPI() 


app.mount("/static",StaticFiles(directory="static"),name="static")



@app.get("/")
def root():
    with open("templates/bulk-payment-v2.html", "r") as file:
        html_content = file.read()
        return HTMLResponse(content=html_content, status_code=200)

@app.post("/verify-bank-account")
def verify_bank_account(request: Request, details: VerifyAccountDetails):
    """Verify bank account details using Flutterwave API"""

    account_number = details.account_number
    bank_code = details.bank_code

    """
    if "user_id" not in request.session:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
        }
    """
    flw_secret_key = os.getenv("FLUTTER_SECRET_API_KEY")
    
    url = "https://api.flutterwave.com/v3/accounts/resolve"
    
    headers = {
        "Authorization": f"Bearer {flw_secret_key}",
        "Content-Type": "application/json"
    }
    
    
    payload = {
        "account_number": account_number, # e.g., "0690000032"
        "account_bank": bank_code         # e.g., "044" for Access Bank
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response_data = response.json()
        
        if response_data.get("status") == "success":
    
            account_name = response_data["data"]["account_name"]
            
            print(f"Success! Name: {account_name}")
            return {"status": "success", "account_name": account_name}
            
        else:
            print(f"Failed: {response_data.get('message')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Connection Error: {e}")
        return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1",port=8000)


