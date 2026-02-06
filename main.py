from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
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

# ==========================================================
# MODELS
# ==========================================================

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    sku = Column(String, index=True)
    description = Column(String)


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    storage_type = Column(String)   # Chiller, Freezer, Dry, Ambient
    bin_name = Column(String)       # A1, FZ-01, etc


class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"))
    location_id = Column(Integer, ForeignKey("locations.id"))
    quantity = Column(Integer, default=0)


class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer)
    location_id = Column(Integer)
    type = Column(String)  # INBOUND / OUTBOUND
    quantity = Column(Integer)
    partner = Column(String)
    date = Column(String, default=lambda:
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


Base.metadata.create_all(bind=engine)

# ==========================================================
# INIT LOCATIONS (RUN ONCE)
# ==========================================================

@app.get("/init-locations")
def init_locations():
    db = SessionLocal()

    if db.query(Location).count() == 0:
        locations = [
            Location(storage_type="Chiller", bin_name="CH-01"),
            Location(storage_type="Freezer", bin_name="FZ-01"),
            Location(storage_type="Dry", bin_name="DR-01"),
            Location(storage_type="Ambient", bin_name="AM-01"),
        ]
        db.add_all(locations)
        db.commit()

    db.close()
    return {"message": "Locations created"}

# ==========================================================
# HOME
# ==========================================================

@app.get("/", response_class=HTMLResponse)
def read_inventory(request: Request):
    db = SessionLocal()

    items = db.query(Item).all()
    locations = db.query(Location).all()

    inventory_data = []

    for item in items:

        # Calculate total quantity across all bins
        stocks = db.query(Stock).filter(Stock.item_id == item.id).all()
        total_quantity = sum(s.quantity for s in stocks)

        movements = db.query(Movement).filter(
            Movement.item_id == item.id
        ).order_by(Movement.id.desc()).all()

        inventory_data.append({
            "item": item,
            "total_quantity": total_quantity,
            "stocks": stocks,
            "movements": movements
        })

    db.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "inventory": inventory_data,
        "locations": locations
    })

# ==========================================================
# ADD ITEM
# ==========================================================

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

# ==========================================================
# INBOUND (WITH LOCATION)
# ==========================================================

@app.post("/inbound/{item_id}")
def inbound(
    item_id: int,
    location_id: int = Form(...),
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()

    if quantity > 0:
        stock = db.query(Stock).filter(
            Stock.item_id == item_id,
            Stock.location_id == location_id
        ).first()

        if not stock:
            stock = Stock(
                item_id=item_id,
                location_id=location_id,
                quantity=0
            )
            db.add(stock)

        stock.quantity += quantity

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

# ==========================================================
# OUTBOUND (WITH LOCATION)
# ==========================================================

@app.post("/outbound/{item_id}")
def outbound(
    item_id: int,
    location_id: int = Form(...),
    quantity: int = Form(...),
    partner: str = Form(...)
):
    db = SessionLocal()

    stock = db.query(Stock).filter(
        Stock.item_id == item_id,
        Stock.location_id == location_id
    ).first()

    if stock and quantity > 0 and stock.quantity >= quantity:

        stock.quantity -= quantity

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
