from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# Database setup
def init_db():
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT,
            description TEXT,
            quantity INTEGER
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory")
    items = cursor.fetchall()
    conn.close()
    return templates.TemplateResponse("index.html", {"request": request, "items": items})

@app.post("/add")
def add_item(sku: str = Form(...), description: str = Form(...), quantity: int = Form(...)):
    conn = sqlite3.connect("inventory.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO inventory (sku, description, quantity) VALUES (?, ?, ?)",
                   (sku, description, quantity))
    conn.commit()
    conn.close()
    return RedirectResponse("/", status_code=303)
Added dashboard UI
