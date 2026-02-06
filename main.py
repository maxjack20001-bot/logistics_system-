
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3

app = FastAPI(title="Integrated Logistics System")

DB = "logistics.db"

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT,
                    description TEXT,
                    quantity INTEGER
                )''')
                
    c.execute('''CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    vehicle TEXT,
                    driver TEXT,
                    status TEXT
                )''')
    
    conn.commit()
    conn.close()

init_db()

class Inbound(BaseModel):
    sku: str
    description: str
    quantity: int

class Outbound(BaseModel):
    sku: str
    quantity: int

class Trip(BaseModel):
    order_id: str
    vehicle: str
    driver: str
    status: str

@app.post("/inbound")
def add_inbound(data: Inbound):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO inventory (sku, description, quantity) VALUES (?, ?, ?)",
              (data.sku, data.description, data.quantity))
    conn.commit()
    conn.close()
    return {"message": "Inbound recorded successfully"}

@app.post("/outbound")
def process_outbound(data: Outbound):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT quantity FROM inventory WHERE sku = ?", (data.sku,))
    result = c.fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="SKU not found")
    
    if result[0] < data.quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    
    new_qty = result[0] - data.quantity
    c.execute("UPDATE inventory SET quantity = ? WHERE sku = ?", (new_qty, data.sku))
    conn.commit()
    conn.close()
    
    return {"message": "Outbound processed", "remaining_stock": new_qty}

@app.post("/trip")
def create_trip(data: Trip):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("INSERT INTO trips (order_id, vehicle, driver, status) VALUES (?, ?, ?, ?)",
              (data.order_id, data.vehicle, data.driver, data.status))
    conn.commit()
    conn.close()
    return {"message": "Trip created successfully"}

@app.get("/inventory")
def view_inventory():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM inventory")
    rows = c.fetchall()
    conn.close()
    return rows

@app.get("/trips")
def view_trips():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT * FROM trips")
    rows = c.fetchall()
    conn.close()
    return rows
