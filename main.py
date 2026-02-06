from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

app = FastAPI()

templates = Jinja2Templates(directory="templates")

# ------------------------
# DATABASE SETUP
# ------------------------

DATABASE_URL = "sqlite:///./inventory.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    description = Column(String)
    quantity = Column(Integer)

Base.metadata.create_all(bind=engine)

# ------------------------
# ROUTES
# ------------------------

@app.get("/", response_class=HTMLResponse)
def read_inventory(request: Request):
    db = SessionLocal()
    items = db.query(Item).all()
    db.close()
    return templates.TemplateResponse("index.html", {"request": request, "inventory": items})

@app.post("/add")
def add_item(sku: str = Form(...), description: str = Form(...), quantity: int = Form(...)):
    db = SessionLocal()
    new_item = Item(sku=sku, description=description, quantity=quantity)
    db.add(new_item)
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)

@app.post("/delete/{item_id}")
def delete_item(item_id: int):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()
    if item:
        db.delete(item)
        db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)

