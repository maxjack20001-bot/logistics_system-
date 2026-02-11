from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import ( Column, Integer, String, ForeignKey,
    create_engine, or_, case
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from services.inventory_service import calculate_stock

import os


app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================================================
# MODELS
# =========================================================

class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    location = Column(String, nullable=False)

    items = relationship(
        "Item",
        back_populates="warehouse",
        cascade="all, delete-orphan"
    )


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    description = Column(String)
    quantity = Column(Integer)

    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    warehouse = relationship("Warehouse", back_populates="items")

    movements = relationship(
        "Movement",
        back_populates="item",
        cascade="all, delete-orphan"
    )


from sqlalchemy import DateTime
from datetime import datetime

class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)

    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    type = Column(String, nullable=False)  # INBOUND / OUTBOUND
    quantity = Column(Integer, nullable=False)
    partner = Column(String, nullable=False)

    date = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item", back_populates="movements")


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


Base.metadata.create_all(bind=engine)

# =========================================================
# HOME
# =========================================================
@app.get("/", response_class=HTMLResponse)
def read_inventory(request: Request, search: str = ""):
    db = SessionLocal()

    warehouses = db.query(Warehouse).all()

    if search:
        items = (
            db.query(Item)
            .options(joinedload(Item.warehouse))
            .filter(
                or_(
                    Item.sku.contains(search),
                    Item.description.contains(search)
                )
            )
            .all()
        )
    else:
        items = (
            db.query(Item)
            .options(joinedload(Item.warehouse))
            .all()
        )

    inventory_data = []
    total_quantity = 0
    total_in = 0
    total_out = 0

    for item in items:
        stock = calculate_stock(db, item.id)

        movements = db.query(Movement).filter(
            Movement.item_id == item.id
        ).order_by(Movement.id.desc()).all()

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

        total_quantity += stock
        total_in += sum(m.quantity for m in item_total_in)
        total_out += sum(m.quantity for m in item_total_out)

        inventory_data.append({
            "item": item,
            "stock": stock,
            "last_in": last_in,
            "last_out": last_out,
            "movements": movements
        })

    low_stock_count = sum(
        1 for row in inventory_data if row["stock"] < 10
    )

    db.close()

    return templates.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "inventory_data": inventory_data,
            "warehouses": warehouses,
            "low_stock_count": low_stock_count,
            "search": search,
            "total_quantity": total_quantity,
            "total_in": total_in,
            "total_out": total_out
        }
    )



# =========================================================
# ITEM CRUD
# =========================================================

@app.post("/add")
def add_item(
    warehouse_id: int = Form(...),
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()

    # Safety check: warehouse must exist
    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        db.close()
        return RedirectResponse("/", status_code=303)

    db.add(Item(
        sku=sku,
        description=description,
        quantity=quantity,
        warehouse_id=warehouse_id
    ))

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
# WAREHOUSES
# =========================================================

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
    location: str = Form(...)
):
    db = SessionLocal()

    db.add(Warehouse(name=name, location=location))
    db.commit()
    db.close()

    return RedirectResponse("/warehouses", status_code=303)
