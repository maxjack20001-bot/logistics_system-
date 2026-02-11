 from sqlalchemy import func
from models import Movement

def calculate_stock(db, item_id):
    total_in = db.query(func.sum(Movement.quantity))\
        .filter(Movement.item_id == item_id,
                Movement.type == "INBOUND").scalar() or 0

    total_out = db.query(func.sum(Movement.quantity))\
        .filter(Movement.item_id == item_id,
                Movement.type == "OUTBOUND").scalar() or 0

    return total_in - total_out

