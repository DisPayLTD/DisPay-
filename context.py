from contextvars import ContextVar
from sqlalchemy.orm import Session
from typing import Dict

db_session:ContextVar[Session] = ContextVar("db_session",default = None)
user_id:ContextVar[Dict] = ContextVar("user_id",default = None)

def set_db_session(session:Session):
	db_session.set(session)

def get_db_session() -> Session:
	return db_session.get()


def set_user_id(user:Dict):
	user_id.set(user)

def get_user_id() -> Dict:
	return user_id.get()
