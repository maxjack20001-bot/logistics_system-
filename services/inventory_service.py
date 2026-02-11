from models import Movement

def calculate_stock(db, item_id: int):
    inbound = db.query(Movement).filter(
        Movement.item_id == item_id,
        Movement.type == "INBOUND"
    ).all()

    outbound = db.query(Movement).filter(
        Movement.item_id == item_id,
        Movement.type == "OUTBOUND"
    ).all()

    total_in = sum(m.quantity for m in inbound)
    total_out = sum(m.quantity for m in outbound)

    return total_in - total_out
