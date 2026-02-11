from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker, joinedload

from services.inventory_service import calculate_stock
from models import Base, Warehouse, Item, Movement, Zone, Bin, Stock

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


Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(bind=engine)




# =========================================================
# HOME
# =========================================================
@app.post("/add")
def add_item(
    warehouse_id: int = Form(...),
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()

    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        db.close()
        return RedirectResponse("/", status_code=303)

    # 1️⃣ Create item with ZERO quantity
    new_item = Item(
        sku=sku,
        description=description,
        quantity=0,   # 🔥 important
        warehouse_id=warehouse_id
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    # 2️⃣ Create initial inbound movement
    if quantity > 0:
        db.add(Movement(
            item_id=new_item.id,
            type="INBOUND",
            quantity=quantity,
            partner="Initial Stock"
        ))
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)


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

    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        db.close()
        return RedirectResponse("/", status_code=303)

    # 1️⃣ Create item with ZERO quantity
    new_item = Item(
        sku=sku,
        description=description,
        quantity=0,
        warehouse_id=warehouse_id
    )

    db.add(new_item)
    db.commit()

    # 2️⃣ Create initial INBOUND movement
    if quantity > 0:
        db.add(Movement(
            item_id=new_item.id,
            type="INBOUND",
            quantity=quantity,
            partner="Initial Stock"
        ))
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)

# =========================================================
# INBOUND
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
        db.add(Movement(
            item_id=item_id,
            type="INBOUND",
            quantity=quantity,
            partner=partner
        ))
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)


# =========================================================
# OUTBOUND
# =========================================================

@app.post("/outbound/{item_id}")
def outbound(
    item_id: int,
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()

    current_stock = calculate_stock(db, item_id)

    if item and quantity > 0 and current_stock >= quantity:
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
   

