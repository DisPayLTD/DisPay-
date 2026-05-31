from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
import requests
from typing import List
from langgraph.checkpoint.memory import InMemorySaver
from langchain_core.utils.uuid import uuid7
from tabulate import tabulate
import os 



api = os.getenv("FLUTTER_SECRET_API_KEY")
llm_api = os.getenv("LLM_API_KEY")
@tool
def send_money(bank_name:List[str],account_number:List[str],amount:List[float],narration:List[str]):
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
  for account_number,bank_name,amount,narration in zip(account_number,bank_name, amount, narration):
    bank_code = bank_codes.get(bank_name)
    
    payload = {
    "account_number":account_number,
    "account_bank": bank_code,
    "amount": amount,
    "narration": narration,
    "currency": "NGN"
    }
    try:
      response = requests.post(
      f"{url}/transfers",
      headers = headers,
      json = payload
      )
      print(response)
      res_json = response.json()
      
      if res_json.get("status") == "success":
        table_rows_success.append([raw_bank_name, acc_num, amt, narr])
      else:
        table_rows_failed.append([bank_name, account_number, amount, narration])
      responses.append(response.json())
    except requests.exceptions.RequestException as e:
      errors.append(f"error {e} has occured")
  success = [response for response in responses if response["status"] == "success"]
  failed =  [response for response in responses if response["status"] == "error"]
  headers = ["Name","Account Number","Account Name"]
  suc_data = [[(r.get("data").get("account_number"),r.get("data").get("amount")) for r in success]]
  obj_success = tabulate(table_rows_failed,headers = headers,tblfmt = "html")

  return {
  "Total_transactions": len(account_number),
  "Processed" : len(responses),
  "Success" :len(success),
  "Failed":len(failed),
  "html_table":table_rows_failed, #for now
  "Details_success": {
  "Account_number": [detail.get("data").get("account_number") for detail in success],
  "Transaction_ID": [detail.get("data").get("id") for detail in success],
  "Amount" : [detail.get("data").get("amount") for detail in success]
  },
  "Details_failed":{
  "Data": [detail.get("data") for detail in failed],
  "Message" :[msg["message"] for msg in failed]
  }
  }



class SalaryAgentPayer:
  def __init__(self,tools):
   system_prompt = ("""
   you are a salary payer assistant  use your available tools to perform tasks. write the appropriate name of a bank exactly as written here 
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
   model = "gemini-2.5-flash",
   api_key = llm_api
   )
   self.checkpointer = InMemorySaver()

   self.agent = create_agent(
   model = llm,
   system_prompt = system_prompt,
   tools = tools,
   checkpointer = self.checkpointer
   )
   self.config = {"configurable":{"thread_id":str(uuid7())}}
  def command(self,prompt):
   output = self.agent.invoke(
   {
   "messages":[{"role":"user","content":prompt}]
   },
   config = self.config
   )

   return output 


tools = [send_money]
