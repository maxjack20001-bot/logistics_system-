from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Warehouse(Base):
    __tablename__ = "warehouses"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    location = Column(String, nullable=False)
    items = relationship("Item", back_populates="warehouse", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    sku = Column(String, index=True)
    description = Column(String)
    quantity = Column(Integer)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    warehouse = relationship("Warehouse", back_populates="items")
    movements = relationship("Movement", back_populates="item", cascade="all, delete-orphan")


class Movement(Base):
    __tablename__ = "movements"
    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    type = Column(String, nullable=False)
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
