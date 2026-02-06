from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, or_, case
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

DATABASE_URL = "sqlite:///./inventory.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ---------------- MODELS ---------------- #

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    description = Column(String)
    quantity = Column(Integer, default=0)   # total quantity


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    storage_type = Column(String)   # Chiller, Freezer, Dry, Ambient
    bin_name = Column(String)       # A1, FZ-01 etc


class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer)
    location_id = Column(Integer)
    quantity = Column(Integer, default=0)


class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer)
    location_id = Column(Integer)   # NEW
    type = Column(String)  # INBOUND / OUTBOUND
    quantity = Column(Integer)
    partner = Column(String)
    date = Column(String, default=lambda:
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


Base.metadata.create_all(bind=engine)


# ---------------- HOME ---------------- #

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

        movements = db.query(Movement).filter(
            Movement.item_id == item.id
        ).order_by(
            case(
                (Movement.type == "INBOUND", 0),
                else_=1
            ),
            Movement.id.desc()
        ).all()

        stocks = db.query(Stock).filter(
            Stock.item_id == item.id
        ).all()

        inventory_data.append({
            "item": item,
            "movements": movements,
            "stocks": stocks
        })

    locations = db.query(Location).all()

    db.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "inventory": inventory_data,
        "locations": locations
    })


# ---------------- ADD ITEM ---------------- #

@app.post("/add")
def add_item(
    sku: str = Form(...),
    description: str = Form(...)
):
    db = SessionLocal()
    db.add(Item(sku=sku, description=description))
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)


# ---------------- INBOUND ---------------- #

@app.post("/inbound/{item_id}")
def inbound(
    item_id: int,
    location_id: int = Form(...),
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()

    item = db.query(Item).filter(Item.id == item_id).first()

    if item and quantity > 0:

        # Update total item quantity
        item.quantity += quantity

        # Update stock per location
        stock = db.query(Stock).filter(
            Stock.item_id == item_id,
            Stock.location_id == location_id
        ).first()

        if stock:
            stock.quantity += quantity
        else:
            stock = Stock(
                item_id=item_id,
                location_id=location_id,
                quantity=quantity
            )
            db.add(stock)

        # Add movement
        db.add(Movement(
            item_id=item_id,
            location_id=location_id,
            type="INBOUND",
            quantity=quantity,
            partner=partner
        ))

        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)


# ---------------- OUTBOUND ---------------- #

@app.post("/outbound/{item_id}")
def outbound(
    item_id: int,
    location_id: int = Form(...),
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()

    item = db.query(Item).filter(Item.id == item_id).first()

    stock = db.query(Stock).filter(
        Stock.item_id == item_id,
        Stock.location_id == location_id
    ).first()

    if item and stock and quantity > 0 and stock.quantity >= quantity:

        # Deduct from location stock
        stock.quantity -= quantity

        # Deduct total item quantity
        item.quantity -= quantity

        db.add(Movement(
            item_id=item_id,
            location_id=location_id,
            type="OUTBOUND",
            quantity=quantity,
            partner=partner
        ))

        db.commit()

    db.close()
    return RedirectResponse("/", status_code=303)
