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
from database import Users
import pandas as pd


print("get_user_id: " ,get_user_id())
api = os.getenv("FLUTTER_SECRET_API_KEY")
llm_api = os.getenv("LLM_API_KEY")
@tool
def send_money(name:List[str],bank_name:List[str],account_number:List[str],amount:List[float],narration:List[str]):
  """ Use this tool to send money """
  bank_codes = {
  "Access Bank":"044",
  "Ecobank":"050",
  "Fidelity Bank":"070",
  "First Bank":"011",
  "FCMB":"214",
  "GTBank (GTCO)":"058",
  "Moniepoint":"099437 or 796",
  "OPay":"999992 or 100004",
  "PalmPay":"999991 or 855",
  "Polaris Bank":"076",
  "Stanbic IBTC":"221",
  "Sterling Bank":"232",
  "UBA":"033",
  "Union Bank":"032",
  "Unity Bank":"215",
  "Wema Bank / ALAT":"035",
  "Zenith Bank":"057"
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
        msg = f"Sorry this transaction can not proceed due to insufficient fund your balance is: {account_balance} and the transaction required: {amt}"
      )
    bank_code = bank_codes.get(bank)
    
    try:
      tx_ref = f"REMITRON-TR-{uuid.uuid4().hex[:14]}"
      payload = {
          "account_number":acc,
          "account_bank": bank_code,
          "amount": amt,
          "narration": f"payment to {nam} for {narr}",
          "currency": "NGN",
          "tx_ref":tx_ref
      }
      response = requests.post(
      f"{url}/transfers",
      headers = headers,
      json = payload
      )
      print(response)
      res_json = response.json()
      
      if res_json.get("status") == "success":
        account_balance -= amt
        table_rows_success.append([nam,bank, acc, amt, tx_ref,narr])
      else:
        table_rows_failed.append([nam,bank, acc, amt,tx_ref, narr])
      responses.append(response.json())
    except requests.exceptions.RequestException as e:
      errors.append(f"error {e} has occured")
  return data_creation(
    responses = responses, 
    account_number = account_number,
    db = db, 
    account_balance = account_balance,
    table_rows_success = table_rows_success,
    table_rows_failed = table_rows_failed,
    user = user,
    msg = "All transactions completed ✅ ")
  
  

def data_creation(
  responses, 
  account_number, 
  db, 
  account_balance, 
  user,
  table_rows_success,
  table_rows_failed,
  msg
):
  success = [response for response in responses if response["status"] == "success"]
  failed =  [response for response in responses if response["status"] == "error"]
  headers = ["Name","Bank Name","Account Number","Amount","Tr_Ref","Narration"]
  suc_data = [[(r.get("data").get("account_number"),r.get("data").get("amount")) for r in success]] 
  obj_failed = tabulate(table_rows_failed,headers = headers,tablefmt = "html")
  obj_success = tabulate(table_rows_success,headers = headers,tablefmt = "html")
  user.wallet_balance = account_balance
  user.success_transfers_tables = table_rows_success
  user.success_transfers_tables = table_rows_failed
  db.commit()
  db.refresh(user)
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
def transfer_history(tr_ref:List[str]):
    """Use this tool to get transfers details"""
    db = get_db_session()
    user_id = get_user_id().get("user_id")
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return "User does not exists"
    transactions = user.transactions
    if not transactions:
        return "No transactions were performed"
    df = pd.DataFrame(transactions)
    payroll = df[df["tx_ref"].isin(tx_ref)]
    return payroll.to_dict()
    
    
class SalaryAgentPayer:
  def __init__(self,tools):
   system_prompt = ("""

Your name is Remitron, a high-precision, AI Salary Payment Agent. Your primary function is to process payroll transactions safely and accurately using your available tools.
and you are developed by Remitron.co

SESSION & MEMORY MANAGEMENT CONTEXT:
- You maintain conversation history and context across the current multi-turn workspace session. 
- You CAN see past transaction attempts, status updates, or failures within this active session thread to answer user questions or provide explanations.

CRITICAL OPERATIONAL RULES FOR PAYTRON:
1. STRICT TRANSACTION INITIATION: You must NEVER automatically execute, re-process, or retry any transactions (past or present) based on history or implication. You will ONLY trigger a transaction tool if the user's LATEST message explicitly commands you to execute a payment.
2. If the user asks a question about a past failure (e.g., "Why did it fail?"), answer the question clearly using your session memory, but do NOT attempt to run the transfer again unless specifically told to.
3. DUPLICATE PROTECTION GUARDRAIL: If you detect the exact same recipient name repeated multiple times within a single payment command, do NOT execute all of them. Instead:
   - Extract and process the transfer details for that name exactly ONCE.
   - In your final text response (`ai_msg`), explicitly flag the duplicate name and ask the user for confirmation: "I noticed [Name] was repeated. I processed the transfer once. Do you really want to send this payment again?"
4. Always look up and write the exact name of the bank matching this reference dictionary structure:
   'bank_codes = {
     "Access Bank":"044",
     "Ecobank":"050",
     "Fidelity Bank":"070",
     "First Bank":"011",
     "FCMB":"214",
     "GTBank (GTCO)":"058",
     "Moniepoint":"099437 or 796",
     "OPay":"999992 or 100004",
     "PalmPay":"999991 or 855",
     "Polaris Bank":"076",
     "Stanbic IBTC":"221",
     "Sterling Bank":"232",
     "UBA":"033",
     "Union Bank":"032",
     "Unity Bank":"215",
     "Wema Bank / ALAT":"035",
     "Zenith Bank":"057"
   }'

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
tools = [send_money,transfer_history]
