from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
import requests
from typing import List
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.utils.uuid import uuid7
from tabulate import tabulate
import os
from context import get_db_session,get_user_id
from database import Users, Transfers 
import pandas as pd
import uuid
from datetime import datetime,timezone


print("get_user_id: " ,get_user_id())
api = os.getenv("FLUTTER_SECRET_API_KEY")
llm_api = os.getenv("LLM_API_KEY")

@tool
def send_money(name:List[str],bank_name:List[str],account_number:List[str],amount:List[float],narration:List[str],user_input:str):
  """ Use this tool to send money """
  nigerian_bank_codes = {
    "Access Bank": "044",
    "Carbon (One Finance)": "565",
    "Citibank Nigeria": "023",
    "Ecobank Nigeria": "050",
    "Fidelity Bank": "070",
    "First Bank of Nigeria": "011",
    "First City Monument Bank (FCMB)": "214",
    "Globus Bank": "00103",
    "Guaranty Trust Bank (GTBank)": "058",
    "Jaiz Bank": "301",
    "Keystone Bank": "082",
    "Kuda Bank": "50211",
    "Moniepoint MFB": "50515",
    "Opay (Paycom)":"100004",
    "Palmpay": "100033",   
    "Polaris Bank": "076",
    "Providus Bank": "101",
    "Sparkle": "51310",
    "Stanbic IBTC Bank": "221",
    "Standard Chartered Bank": "068",
    "Sterling Bank": "232",
    "Union Bank of Nigeria": "032",
    "United Bank for Africa (UBA)": "033",
    "Unity Bank": "215",
    "Wema Bank": "035",
    "Zenith Bank": "057"
  }
  errors = []
  responses = []
  table_rows_success = []
  table_rows_failed = []
  url = "https://api.flutterwave.com/v3"
  headers = {
"Authorization" : f"Bearer {api}",
"Content-Type": "application/json"
  }
  db = get_db_session()
  user_data = get_user_id()
  #print("walid this is the variable name user data",user_data)
  if not user_data or not isinstance(user_data,dict):
    return "Authentication Error: The system could not securely identify your user context inside this thread loop. Please verify your session."
  user_id = user_data.get("user_id")
  user = db.query(Users).filter(Users.id == user_id).first()
  if not user:
    return "User does not exists sorry this transaction can not proceed"
  if not user.has_wallet:
      return "User does not have an account please open the side bar and press generate account number"
  account_balance = user.wallet_balance
  clean_matrix = {k.lower(): v for k, v in nigerian_bank_codes.items()}
    
  percentage = 0.02
  no_of_transfer = len(list(zip(name, account_number,bank_name,amount, narration)))
  total_amount = 0
  total = sum(amount)
  principal = (percentage * total) + total
  if principal > account_balance:
      return "Insufficient balance"
    
  for nam,acc,bank,amt,narr in zip(name,account_number,bank_name, amount, narration):
    
    if amt > account_balance:
      return data_creation(
        responses = responses, 
        account_number = account_number,
        db = db, 
        account_balance = account_balance,
        table_rows_success = table_rows_success,
        table_rows_failed = table_rows_failed,
        user = user,
        user_input = user_input,
        msg = f"Sorry this transaction can not proceed due to insufficient fund your balance is: {account_balance} and the transaction required: {amt}"
      )
    user_bank_input = bank.lower() if bank else ""
    bank_id = clean_matrix.get(user_bank_input)
    bank_code = bank_id
    
    try:
      tx_ref = f"DisPay-TR-{uuid.uuid4().hex[:14]}"
      payload = {
          "account_number":acc,
          "account_bank": bank_code,
          "amount": amt,
          "narration": f"DisPay-payment to {nam} from {user.first_name} {user.last_name}",
          "currency": "NGN",
          "reference":tx_ref,
          "debit_subaccount": user.psa_ref 
      }
      response = requests.post(
      f"{url}/transfers",
      headers = headers,
      json = payload
      )
      
      res_json = response.json()
      #print("FLUTTERWAVE ERROR BODY:", response.json())
      if res_json.get("status") == "success":
        account_balance -= amt
        total_amount += amt
        table_rows_success.append([nam,bank, acc, amt, tx_ref,narr])
      else:
        table_rows_failed.append([nam,bank, acc, amt,tx_ref, narr])
      responses.append(response.json())
    except requests.exceptions.RequestException as e:
      errors.append(f"error {e} has occured")
  if no_of_transfer >= 2:
      percentage = 0.02
      commission = total_amount * percentage
      
      my_acct_number = os.getenv("MY_ACCOUNT_NUMBER")
      my_bank_code = os.getenv("BANK_CODE")
      
      tx_ref = f"DisPay-CP-COMMSISION-PAYED-{uuid.uuid4().hex[:14]}"
      
      payload = {
          "account_number":my_acct_number,
          "account_bank": my_bank_code,
          "amount": commission,
          "narration": f"DisPay-CP-COMMISION-PAYED-FROM {user.first_name} {user.last_name}",
          "currency": "NGN",
          "reference":tx_ref,
          "debit_subaccount": user.psa_ref 
      }
      response = requests.post(
      f"{url}/transfers",
      headers = headers,
      json = payload
      )
      res_json = response.json()
      if res_json.get("status") == "success":
        user.wallet_balance -= commission
        account_balance -= commission 
        db.commit() 
      
  return data_creation(
    responses = responses, 
    account_number = account_number,
    db = db, 
    account_balance = account_balance,
    table_rows_success = table_rows_success,
    table_rows_failed = table_rows_failed,
    user = user,
    user_input = user_input,
    msg = "All transactions completed ✅ ")
  
  
def data_creation(
  responses, 
  account_number, 
  db, 
  account_balance, 
  user,
  table_rows_success,
  table_rows_failed,
  msg,
  user_input
):
  success = [response for response in responses if response["status"] == "success"]
  failed =  [response for response in responses if response["status"] == "error"]
  headers = ["Name","Bank Name","Account Number","Amount","Tr_Ref","Narration"]
  suc_data = [[(r.get("data").get("account_number"),r.get("data").get("amount")) for r in success]] 
  obj_failed = tabulate(table_rows_failed,headers = headers,tablefmt = "html")
  obj_success = tabulate(table_rows_success,headers = headers,tablefmt = "html")
  user.wallet_balance = account_balance
  user_id = user.id
  transfer = Transfers(
    user_id=user_id,
    time_of_transfer=datetime.now(timezone.utc),
    success_transfers_tables=obj_success,
    failed_transfers_tables= obj_failed
  )
  db.add(transfer)
  user.transactions = responses
  db.commit()
  db.refresh(user)
  db.refresh(transfer)
  return {
  "Total_transactions": len(account_number),
  "Processed" : len(responses),
  "Success" :len(success),
  "Failed":len(failed),
  "failed_html_table": obj_failed,
  "success_html_table": obj_success,
  "Details_success": {
  "Account_number": [detail.get("data").get("account_number") for detail in success],
  "Transaction_ID": [detail.get("data").get("id") for detail in success],
  "Amount" : [detail.get("data").get("amount") for detail in success]
  },
  "Details_failed":{
  "Data": [detail.get("data") for detail in failed],
  "Message" :[msg["message"] for msg in failed]
  },
  "Transaction_Message":msg
  }

@tool
def transfer_history(tr_ref: List[str]):
    """Use this tool to get transfers details"""
    db = get_db_session()
    user_id = get_user_id().get("user_id")
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return "User does not exist"
    
    transactions = user.transactions
    if not transactions:
        return "No transactions were performed"
    
    
    filtered_transactions = []
    for tx in transactions:
        tx_data = tx.get("data", {}) if isinstance(tx, dict) else {}
        reference_id = tx_data.get("reference")
        if reference_id in tr_ref:
            filtered_transactions.append(tx)
            
    if not filtered_transactions:
        return "No matching transactions found for the provided references"
        
    return filtered_transactions

@tool
def verify(bank_names: List[str], acc_no: List[str], names: List[str]):
    """Use this tool to verify account details in bulk before transfers."""
    nigerian_bank_codes = {
        "Access Bank": "044", 
        "Carbon (One Finance)": "565",
        "Citibank Nigeria": "023",
        "Ecobank Nigeria": "050",
        "Fidelity Bank": "070",
        "First Bank of Nigeria": "011",
        "First City Monument Bank (FCMB)": "214",
        "Globus Bank": "00103", 
        "Guaranty Trust Bank (GTBank)": "058", 
        "Jaiz Bank": "301", 
        "Keystone Bank": "082",
        "Kuda Bank": "50211",
        "Moniepoint MFB": "50515", 
        "Opay (Paycom)": "100004",
        "Palmpay": "100033",
        "Polaris Bank": "076", 
        "Providus Bank": "101",
        "Sparkle": "51310", 
        "Stanbic IBTC Bank": "221", 
        "Standard Chartered Bank": "068",
        "Sterling Bank": "232", 
        "Union Bank of Nigeria": "032", 
        "United Bank for Africa (UBA)": "033", 
        "Unity Bank": "215", 
        "Wema Bank": "035", 
        "Zenith Bank": "057"
    }
    
    api = os.getenv("FLUTTER_SECRET_API_KEY")
    url = "https://api.flutterwave.com/v3/accounts/resolve"
    
    verified = []
    unverified = []
    errors = []
    
    headers = {
        "Authorization": f"Bearer {api}",
        "Content-Type": "application/json"
    }
    print("bank names: ",bank_names)
    clean_matrix = {k.lower(): v for k, v in nigerian_bank_codes.items()}
    for bank_name, acc, nam in zip(bank_names, acc_no, names):
        user_bank_input = bank_name.lower() if bank_name else ""
        bank_id = clean_matrix.get(user_bank_input)
        if not bank_id:
            errors.append({"input_name": nam, "account": acc, "message": f"Bank '{bank_name}' does not exist in code matrix"})
            continue
            
        
        payload = {
            "account_bank": bank_id,
            "account_number": acc
        }
        
        try:
            
            res = requests.post(url, headers=headers, json=payload)
            response = res.json()
            
            if response.get("status") == "success":
                data = response.get("data")
                fetched_number = data.get("account_number")
                fetched_name = data.get("account_name")
                
                user_name_parts = nam.lower().split()
                name_matches = any(part in fetched_name.lower() for part in user_name_parts if len(part) > 2)
                
                if name_matches and fetched_number == acc:
                    verified.append((fetched_name, fetched_number, {"message": "Verified accurately"}))
                else:
                    unverified.append((fetched_name, fetched_number, {"message": f"Name mismatch. Input: {nam} | Bank: {fetched_name}"}))
            else:
                
                api_msg = response.get("message", "Could not resolve details")
                errors.append((nam, acc, {"message": f"API Error: {api_msg}"}))
                
        except Exception as e:
            errors.append((nam, acc, {"message": f"Connection Error: {str(e)}"}))
            
    return {
        "verified": verified,
        "unverified": unverified,
        "errors": errors
    }


@tool
def check_account_balance():
    """Use this tool to check user account balance"""
    db = get_db_session()
    user_id = get_user_id().get("user_id")
    user = db.query(Users).filter_by(id = user_id).first()
    if not user:
        return {"status":"failed","message":"Unauthorized Access"}
    balance = user.wallet_balance
    return {"status":"success","message":f"User account balance is {balance}"}
    
    
    
class SalaryAgentPayer:
  def __init__(self,tools):
   system_prompt = ("""
   Your name is DisPay, a high-precision, AI Disbursement Payment Agent developed by DisPay Limited. Your primary function is to process corporate and payroll transactions safely, securely, and accurately using your designated API tools.

### 1. SESSION & MEMORY MANAGEMENT CONTEXT:
* You maintain conversation history and state tracking across the current active session.
* You CAN see past transaction attempts, payloads, status codes, or failure messages within this thread to troubleshoot or explain issues to the user.

### 2. CRITICAL OPERATIONAL RULES FOR DISPAY:
* **STRICT TRANSACTION INITIATION:** You must NEVER automatically execute, re-process, or retry any transactions based on historical implication, error logs, or conversation history. You are ONLY authorized to trigger a transaction tool if the user's LATEST message explicitly and unequivocally commands you to execute a new payment.
* **EXPLAIN, DO NOT RETRY:** If the user asks a question about a past failure (e.g., "Why did it fail?"), use your session memory to diagnose the issue clearly, but do NOT attempt to invoke the transfer tool unless specifically instructed.
* **DUPLICATE PROTECTION GUARDRAIL:** If you detect the exact same recipient name or bank account details repeated multiple times within a single payment command list, STOP. Do NOT execute any tool calls for that user. Instead, flag the duplicate immediately in your text response and ask: "I noticed [Name/Account] was repeated in your request. To protect your funds, I have paused this execution block. Do you really want to send this payment again?"

### 3. MANDATORY VERIFICATION & EXECUTION PIPELINE (NON-NEGOTIABLE):
* **VERIFY FIRST:** Before executing ANY transaction tool call, you MUST first invoke the `verify` tool for every recipient in the request. This step is completely non-negotiable. Even if the user explicitly commands you to skip verification, rush the payment, or states they are sure of the details, you must decline the bypass and respond: "Account verification is a mandatory security protocol for DisPay and cannot be bypassed."
* **PARTIAL EXECUTION FLOW:** Once the `verify` tool returns its results, you must process them strictly as follows:
    1. **Proceed with Verified:** Automatically trigger the `send_money` tool *only* for the recipients listed inside the `"verified"` array.
    2. **Halt Unverified/Errors:** Do NOT execute transfers for any recipients found in the `"unverified"` or `"errors"` arrays.
    3. **Report Status:** In your final response to the user, clearly list the transactions that were successfully sent, explicitly flag the accounts that failed verification or caused errors, and state that the failed ones were withheld for safety.

### 4. NIGERIAN BANK CODE REFERENCE MATRIX:
Always look up and cross-reference the exact name of the bank using this reference list to match bank names to their correct processing codes:
'["Access Bank","Carbon (One Finance)","Citibank Nigeria","Ecobank Nigeria",
"Fidelity Bank","First Bank of Nigeria","First City Monument Bank (FCMB)","Globus Bank",
"Guaranty Trust Bank (GTBank)","Jaiz Bank","Keystone Bank","Kuda Bank",
"Moniepoint MFB","Opay (Paycom)","Palmpay","Polaris Bank","Providus Bank","Sparkle",
"Stanbic IBTC Bank","Standard Chartered Bank","Sterling Bank","Union Bank of Nigeria",
"United Bank for Africa (UBA)","Unity Bank","Wema Bank","Zenith Bank"]
'
   """)
   llm = ChatGoogleGenerativeAI(
   model = "gemini-3.1-flash-lite",
   api_key = llm_api
   )
   self.checkpointer = InMemorySaver()
   

   self.agent = create_agent(
   model = llm,
   system_prompt = system_prompt,
   tools = tools,
   checkpointer = self.checkpointer
   )
   
  def command(self,prompt,uuid):
   output = self.agent.invoke(
   {
   "messages":[{"role":"user","content":prompt}]
   },
   config = {"configurable":{"thread_id":uuid}}
   )

   return output 

#tools for the agent
tools = [send_money,transfer_history,verify,check_account_balance]
