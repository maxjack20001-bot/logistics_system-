from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, or_
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ------------------------
# DATABASE SETUP
# ------------------------

DATABASE_URL = "sqlite:///./inventory.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ------------------------
# MODELS
# ------------------------

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
    type = Column(String)  # INBOUND or OUTBOUND
    quantity = Column(Integer)
    partner = Column(String)
    date = Column(String, default=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


Base.metadata.create_all(bind=engine)

# ------------------------
# HOME / INVENTORY PAGE
# ------------------------

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

    for item in items:

        # Last INBOUND
        last_in = db.query(Movement).filter(
            Movement.item_id == item.id,
            Movement.type == "INBOUND"
        ).order_by(Movement.id.desc()).first()

        # Last OUTBOUND
        last_out = db.query(Movement).filter(
            Movement.item_id == item.id,
            Movement.type == "OUTBOUND"
        ).order_by(Movement.id.desc()).first()

        inventory_data.append({
            "item": item,
            "last_in": last_in,
            "last_out": last_out
        })

    low_stock_count = db.query(Item).filter(Item.quantity < 10).count()

    db.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "inventory": inventory_data,
        "low_stock_count": low_stock_count,
        "search": search
    })


# ------------------------
# ADD ITEM
# ------------------------

@app.post("/add")
def add_item(
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()
    db.add(Item(
        sku=sku,
        description=description,
        quantity=quantity
    ))
    db.commit()
    db.close()

    return RedirectResponse("/", status_code=303)


# ------------------------
# EDIT ITEM PAGE
# ------------------------

@app.get("/edit/{item_id}", response_class=HTMLResponse)
def edit_page(request: Request, item_id: int):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()
    db.close()

    return templates.TemplateResponse(
        "edit.html",
        {"request": request, "item": item}
    )


# ------------------------
# UPDATE ITEM
# ------------------------

@app.post("/update/{item_id}")
def update_item(
    item_id: int,
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()

    if item:
        item.sku = sku
        item.description = description
        item.quantity = quantity
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)


# ------------------------
# DELETE ITEM
# ------------------------

@app.post("/delete/{item_id}")
def delete_item(item_id: int):
    db = SessionLocal()
    item = db.query(Item).filter(Item.id == item_id).first()

    if item:
        db.delete(item)
        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)


# ------------------------
# INBOUND
# ------------------------

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


# ------------------------
# OUTBOUND
# ------------------------

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


# ------------------------
# MOVEMENT HISTORY PAGE
# ------------------------

@app.get("/movements", response_class=HTMLResponse)
def movement_history(request: Request):
    db = SessionLocal()

    movements = db.query(Movement).order_by(
        Movement.id.desc()
    ).all()

    db.close()

    return templates.TemplateResponse(
        "movements.html",
        {
            "request": request,
            "movements": movements
        }
    )
