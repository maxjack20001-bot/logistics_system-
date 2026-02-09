from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, or_, case
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import os


# ---------------- MODELS ---------------- #

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    description = Column(String)
    quantity = Column(Integer)


class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer)
    type = Column(String)
    quantity = Column(Integer)
    partner = Column(String)
    date = Column(String, default=lambda:
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


# ✅ MOVE THESE HERE (NOT INSIDE outbound)

class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    location = Column(String)


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    warehouse_id = Column(Integer)


class Bin(Base):
    __tablename__ = "bins"

    id = Column(Integer, primary_key=True)
    code = Column(String)
    zone_id = Column(Integer)


class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer)
    bin_id = Column(Integer)
    quantity = Column(Integer, default=0)


# ✅ CREATE TABLES AFTER ALL MODELS
Base.metadata.create_all(bind=engine)
@app.post("/outbound/{item_id}")
def outbound(
    item_id: int,
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()

    if item and quantity > 0 and item.quantity >= quantity:
        item.quantity -= quantity
        db.add(Movement(
            item_id=item_id,
            type="OUTBOUND",
            quantity=quantity,
            partner=partner
        ))
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)
