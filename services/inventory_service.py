 from sqlalchemy import func
from models import Movement

def read_inventory(request: Request, search: str = ""):
    db = SessionLocal()

    items = db.query(Item).all()

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

    return templates.TemplateResponse(...)

