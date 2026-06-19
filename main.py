    file_type = None
        filename = file.filename.lower()
        if filename.endswith(".csv"):
            content = pd.read_csv(io.BytesIO(content))
            file_type = "csv"
        elif filename.endswith(".xlsx") or filename.endswith(".xls"):
            content = pd.read_excel(io.BytesIO(content))
            file_type = "excel"
        else:
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST,
                detail = "document not supported only .csv and .xlsx are allowed"
            )
    except Exception as e:
        return {"status":"failed","message": str(e)}
    df = content
    df.columns = df.columns.str.lower()
    data = [f"{idx + 1}. pay \"{row.name}\" \"{row.get('amount')} \" (NGN)  to  account number \"{row.get('account_number')}\"  \"{row.get('bank_name')}\" bank\n" for idx,row in df.iterrows()]
    data = "".join(data)
    print(data)
    session_id = request.session.get("thread_id")
    if not session_id or "user_id" not in request.session:
        return {
            "status":"failed",
            "message": "user not logged in",
            "url": "/auth"
        }
    
    set_db_session(db_session)
    print("session exists " if db_session else "session_does not exists")
    set_user_id({"user_id": request.session["user_id"]})
    res = agent.command(data, uuid = session_id)
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
    res = {
        "status":"success",
        "message":"file processed successfully",
        "ai_msg":ai_msg,
        "success_html_table": success_html_table,
        "failed_html_table": failed_html_table
    }
    return res


@app.post("/send-money")
@limiter.limit("5/minute")
def send_money(command:Command,request: Request,db: Session=Depends(get_db)):
    if "user_id" not in request.session:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
        }
    idempotency_key = command.idempotency_key
    user_id = request.session.get("user_id")
    existing= db.query(Idempotency).filter(Idempotency.user_id == user_id, Idempotency.idempotency_key == idempotency_key).first()
    if existing:
        return existing.result
    
    session_id = request.session.get("thread_id")
    if not session_id:
        return {
            "status": "failed",
            "message": "user is not logged in",
            "url": "/auth"
        }
    set_db_session(db)
    set_user_id({"user_id": request.session["user_id"]})
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

    result = {"status":"success","ai_msg":ai_msg,"success_html_table": success_html_table,"failed_html_table": failed_html_table}
    new_idempotency = Idempotency(
        user_id = user_id,
        idempotency_key = idempotency_key,
        result = result 
    )
    db.add(new_idempotency)
    db.commit()
    db.refresh(new_idempotency)
    
    return result 
    
tx_ref = f"REMITRON-VA-{str(uuid.uuid4().hex[:16])}"

@app.get("/generate-account-number")
def generate_account_number(req: Request, db: Session = Depends(get_db)):
     
    user_id = req.session.get("user_id")
    if not user_id:
        return {
            "status": "failed",
            "message": "User not logged in",
            "url": "/auth"
        }
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        return {
            "status": "failed",
            "message": "User does not exist please signup or login first",
            "url": "/auth",
        }
    if user.has_wallet:
        return {
            "status": "failed",
            "message": "User already has an account number",
            "url": "/dashboard",
        }
    
    email = user.email
    phone = user.phone_number
    first_name = user.first_name
    last_name = user.last_name
    
    api = os.getenv("FLUTTER_SECRET_API_KEY")
    header = {
        "Authorization": f"Bearer {api}",
        "Content-Type": "application/json"
    }
     
    body = {
        "account_name": f"{first_name} {last_name}", 
        "email": email,
        "mobilenumber": phone,
        "country": "NG",
        "bank_code": "035"                           
    }
    
    url = "https://api.flutterwave.com/v3/payout-subaccounts"

    try:
        res = requests.post(
            url,
            headers=header,
            json=body
        )
        res_json = res.json()
        
        
        if res_json.get("status") == "success":
            data = res_json.get("data", {})
             
            account_number = data.get("nuban")           
            bank_name = data.get("bank_name")             
            psa_ref = data.get("account_reference")       
            
            user.account_number = account_number
            user.bank_name = bank_name
            user.psa_ref = psa_ref
            user.has_wallet = True
            
            db.commit()
            db.refresh(user)
            
            return {
                "status": "success",
                "message": "Wallet successfully created!",
                "url": "/dashboard"
            }
        else:
            return {
                "status": "failed",
                "message": res_json.get("message", "Failed to initialize subaccount wallet container.")
            }
            
    except requests.exceptions.RequestException as e:
        return {"status": "failed", "message": f"An error occurred {str(e)}"}


@app.get("/transaction-history")
async def transaction_history(request: Request, db: Session = Depends(get_db)):
    """Get transaction history"""
    
    try:
        if "user_id" not in request.session:
            raise HTTPException(status_code=401)
        
        # Get user with transfers
        user = db.query(Users).filter(Users.id == request.session["user_id"]).first()
        if not user:
            raise HTTPException(status_code=401)
        
        # Get all transfers sorted by date (newest first)
        transfers = db.query(Transfers).filter(
            Transfers.user_id == user.id
        ).order_by(Transfers.time_of_transfer.desc()).all()
        
        if not transfers:
            return {
                "status": "success",
                "message": "No transactions yet",
                "html": "<p style='text-align: center; color: #999; padding: 30px;'>No transactions yet. Your transaction history will appear here.</p>"
            }
        
        # Build HTML with pagination
        html = "<div class='history-container'>"
        
        for transfer in transfers:
            # Format date
            date_str = transfer.time_of_transfer.strftime("%B %d, %Y at %I:%M %p")
            
            html += f"""
            <div class="history-entry">
                <div class="history-date-header">
                    <h4>📅 {date_str}</h4>
                </div>
                
                <div class="history-tables">
                    <div class="history-table-section">
                        <h5>✅ Successful Transfers</h5>
                        {transfer.success_transfers_tables if transfer.success_transfers_tables else '<p>No successful transfers</p>'}
                    </div>
                    
                    <div class="history-table-section">
                        <h5>❌ Failed Transfers</h5>
                        {transfer.failed_transfers_tables if transfer.failed_transfers_tables else '<p>No failed transfers</p>'}
                    </div>
                </div>
            </div>
            """
        
        html += "</div>"
        
        return {
            "status": "success",
            "message": f"Loaded {len(transfers)} transaction records",
            "html": html
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

# ===== PIN SETUP ROUTE =====
@app.post("/set-transaction-pin")
def set_transaction_pin(request: Request, payload: PinModel, db: Session = Depends(get_db)):
    """Set or update 4-digit transaction PIN"""
    ph = PasswordHassher()
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Not logged in"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    
    # Validate PIN is 4 digits
    if not payload.pin.isdigit() or len(payload.pin) != 4:
        return {"status": "error", "message": "PIN must be exactly 4 digits"}
    
    try:
        # Hash the PIN
        hashed_pin = ph.hash(payload.pin)
        user.transaction_pin = hashed_pin
        db.commit()
        
        return {
            "status": "success",
            "message": "PIN set successfully"
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}


# ===== PIN VERIFICATION ROUTE =====
@app.post("/verify-transaction-pin")
def verify_transaction_pin(request: Request, payload: PinModel, db: Session = Depends(get_db)):
    """Verify 4-digit PIN before payment"""
    
    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "error", "message": "Not logged in"}
    
    user = db.query(Users).filter(Users.id == user_id).first()
    
    if not user.transaction_pin:
        return {"status": "error", "message": "No PIN set"}
    
    try:
        # Verify PIN
        ph.verify(user.transaction_pin, payload.pin)
        return {"status": "success", "message": "PIN verified"}
    except Exception:
        return {"status": "error", "message": "Incorrect PIN"}

@app.get("/set-pin")
def set_pin_page(request: Request):
    """Serve PIN setup page"""
    if "user_id" not in request.session:
        return RedirectResponse(url="/auth", status_code=302)
    
    with open("templates/set-pin.html") as f:
        return HTMLResponse(content=f.read())
