import os
from sqlalchemy import String,Float,create_engine,Column,Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

SQL_URL = os.getenv("DATABASE_URL", "sqlite:///./remitron.db")



Base = declarative_base()


class Users(Base):
	__tablename__ = "users"
	id = Column(Integer,primary_key = True)
	first_name = Column(String,default = "Unknown")
	last_name = Column(String,default = "Unknown")
	email = Column(String)
	password = Column(String)
	nin = Column(String)
	phone_number = Column(String)
	bvn = Column(String)
	customer_id = Column(String)
	account_number = Column(String)
	bank_name = Column(String)
	wallet_balance = Column(Float, default= 0.0)

engine = create_engine(SQL_URL)
sessionLocal = sessionmaker(autocommit = False,autoflush = False,bind = engine)


def get_db():
	db = sessionLocal()
	try:
		yield db
	finally:
		db.close()

def init_db():
	Base.metadata.create_all(bind = engine)
	
	

