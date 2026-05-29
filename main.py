import fastapi
from fastapi import HTMLResponse


app = fastapi()

@app.get("/")
def home():
  with open("templates/index.html") as f:
    return HTMLResponse(content = f.read())
