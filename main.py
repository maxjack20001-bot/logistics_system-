from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, or_, case
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import os

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================================================
# MODELS
# =========================================================

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
    type = Column(String)  # INBOUND / OUTBOUND
    quantity = Column(Integer)
    partner = Column(String)
    date = Column(String, default=lambda:
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

# ---------------- WAREHOUSE STRUCTURE ---------------- #

class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    location = Column(String)


@app.get("/warehouses", response_class=HTMLResponse)
def warehouses_page(request: Request):
    db = SessionLocal()
    warehouses = db.query(Warehouse).all()
    db.close()

    return templates.TemplateResponse(
        "warehouses.html",
        {
            "request": request,
            "warehouses": warehouses
        }
    )


@app.post("/warehouses/add")
def add_warehouse(
    name: str = Form(...),
    location: str = Form(None)
):
    db = SessionLocal()
    warehouse = Warehouse(name=name, location=location)
    db.add(warehouse)
    db.commit()
    db.close()
    return RedirectResponse("/warehouses", status_code=303)



class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True)
    name = Column(String)  # Freezer, Dry, Chiller
    warehouse_id = Column(Integer)


class Bin(Base):
    __tablename__ = "bins"

    id = Column(Integer, primary_key=True)
    code = Column(String)  # A1, FZ-01
    zone_id = Column(Integer)


class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer)
    bin_id = Column(Integer)
    quantity = Column(Integer, default=0)


# Create tables
Base.metadata.create_all(bind=engine)

# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def read_inventory(request: Request, search: str = ""):
    db = SessionLocal()

    if search:
        items = db.query(Item).filter(
            or_(
                Item.sku.contains(search),
                Item.description.contains(search)
            )
        ).all()
    else:
        items = db.query(Item).all()

    inventory_data = []
    total_quantity = 0
    total_in = 0
    total_out = 0

    for item in items:

        movements = db.query(Movement).filter(
            Movement.item_id == item.id
        ).order_by(
            case((Movement.type == "INBOUND", 0), else_=1),
            Movement.id.desc()
        ).all()

        last_in = db.query(Movement).filter(
            Movement.item_id == item.id,
            Movement.type == "INBOUND"
        ).order_by(Movement.id.desc()).first()

        last_out = db.query(Movement).filter(
            Movement.item_id == item.id,
            Movement.type == "OUTBOUND"
        ).order_by(Movement.id.desc()).first()

        item_total_in = db.query(Movement).filter(
            Movement.item_id == item.id,
            Movement.type == "INBOUND"
        ).all()

        item_total_out = db.query(Movement).filter(
            Movement.item_id == item.id,
            Movement.type == "OUTBOUND"
        ).all()

        total_quantity += item.quantity
        total_in += sum(m.quantity for m in item_total_in)
        total_out += sum(m.quantity for m in item_total_out)

        inventory_data.append({
            "item": item,
            "last_in": last_in,
            "last_out": last_out,
            "movements": movements
        })

    low_stock_count = db.query(Item).filter(Item.quantity < 10).count()

    db.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "inventory": inventory_data,
        "low_stock_count": low_stock_count,
        "search": search,
        "total_quantity": total_quantity,
        "total_in": total_in,
        "total_out": total_out
    })


# =========================================================
# ITEM CRUD
# =========================================================

@app.post("/add")
def add_item(
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()
    db.add(Item(sku=sku, description=description, quantity=quantity))
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


# =========================================================
# INBOUND / OUTBOUND
# =========================================================

@app.post("/inbound/{item_id}")
def inbound(
    item_id: int,
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()

    if item and quantity > 0:
        item.quantity += quantity
        db.add(Movement(
            item_id=item_id,
            type="INBOUND",
            quantity=quantity,
            partner=partner
        ))
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)


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


# =========================================================
# WAREHOUSE ROUTES
# =========================================================

@app.post("/add-warehouse")
def add_warehouse(
    name: str = Form(...),
    location: str = Form(...)
):
    db = SessionLocal()
    db.add(Warehouse(name=name, location=location))
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)


@app.post("/add-zone")
def add_zone(
    name: str = Form(...),
    warehouse_id: int = Form(...)
):
    db = SessionLocal()
    db.add(Zone(name=name, warehouse_id=warehouse_id))
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)


@app.post("/add-bin")
def add_bin(
    code: str = Form(...),
    zone_id: int = Form(...)
):
    db = SessionLocal()
    db.add(Bin(code=code, zone_id=zone_id))
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)


@app.post("/assign-stock")
def assign_stock(
    item_id: int = Form(...),
    bin_id: int = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()

    existing = db.query(Stock).filter(
        Stock.item_id == item_id,
        Stock.bin_id == bin_id
    ).first()

    if existing:
        existing.quantity += quantity
    else:
        db.add(Stock(
            item_id=item_id,
            bin_id=bin_id,
            quantity=quantity
        ))

    db.commit()
    db.close()

    return RedirectResponse("/", status_code=303)
