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
      responses.append(response.json())
    except requests.exception.RequestException as e:
      errors.append(f"error {e} has occured")
  success = [response for response in responses if response["status"] == "success"]
  failed =  [response for response in responses if response["status"] == "error"]
  headers = ["Name","Account Number","Account Name"]
  suc_data = [([r.get("data").get("account_number"),r.get("data").get("amount")) for r in responses]]
  obj_success = tabulate(success,headers = headers,tblfmt = "html")

  return {
  "Total_transactions": len(account_number),
  "Processed" : len(responses),
  "Success" :len(success),
  "Failed":len(failed),
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
   system_prompt = ("you are a salary payer assistant  use your available tools to perform tasks")
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
   result = output["messages"][-1].content
   if type(result)== list:
     result = result[0]["text"]


   return result


tools = [send_money]
