from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, joinedload

from services.inventory_service import calculate_stock
from models import Base, Warehouse, Item, Movement
from fastapi.responses import HTMLResponse
from fastapi import Request
from models import User

import os


app = FastAPI()
templates = Jinja2Templates(directory="templates")
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key="super-secret-key-change-this"
)


# =========================================================
# DATABASE
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)

# Create tablesfrom models import Base  # wherever your Base is defined
from models import Base
from models import User
Base.metadata.create_all(bind=engine)


# =========================================================
# LOGIN & ADMIN SYSTEM
# =========================================================

from passlib.context import CryptContext
from fastapi import Form
from fastapi.responses import HTMLResponse, RedirectResponse

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------
# REGISTER USER
# ---------------------------------------------------------
@app.post("/register")
def register(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        db.close()
        return {"error": "Username already exists"}

    new_user = User(
        username=username,
        password_hash=hash_password(password),
        is_admin=0
    )

    db.add(new_user)
    db.commit()
    db.close()

    return {"message": "User created successfully"}


# ---------------------------------------------------------
# LOGIN PAGE
# ---------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# ---------------------------------------------------------
# LOGIN ACTION
# ---------------------------------------------------------
@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()

    if not user:
        db.close()
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"}
        )

    if not verify_password(password, user.password_hash):
        db.close()
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid username or password"}
        )

    request.session["user"] = user.username
    db.close()

    return RedirectResponse("/", status_code=303)


# ---------------------------------------------------------
# CREATE / RESET ADMIN (ONLY FOR TESTING)
# ---------------------------------------------------------
@app.get("/reset-admin")
def reset_admin():
    db = SessionLocal()

    # delete existing admin if exists
    db.query(User).filter(User.username == "admin").delete()
    db.commit()

    # create new admin
    admin = User(
        username="admin",
        password_hash=hash_password("1234"),
        is_admin=1
    )

    db.add(admin)
    db.commit()
    db.close()

    return {"message": "Admin reset successfully"}

# =========================================================
# HOME
# =========================================================

@app.get("/", response_class=HTMLResponse)
def read_inventory(request: Request):

    # 🔒 Protect page
    if "user" not in request.session:
        return RedirectResponse("/login", status_code=303)
       
    db = SessionLocal()

    warehouses = db.query(Warehouse).all()
    items = db.query(Item).options(joinedload(Item.warehouse)).all()

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
            "total_quantity": total_quantity,
            "total_in": total_in,
            "total_out": total_out
        }
    )


# =========================================================
# ADD ITEM
# =========================================================

@app.post("/add")
def add_item(
    warehouse_id: int = Form(...),
    name: str = Form(...),
    sku: str = Form(...),
    description: str = Form(...),
    quantity: int = Form(...)
):
    db = SessionLocal()

    warehouse = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
    if not warehouse:
        db.close()
        return RedirectResponse("/", status_code=303)

    # Create item with zero quantity (stock calculated from movements)
    new_item = Item(
        name=name,
        sku=sku,
        description=description,
        quantity=0,
        warehouse_id=warehouse_id
    )

    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    # Create initial inbound movement
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
