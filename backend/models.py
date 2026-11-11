from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, ForeignKey, ForeignKeyConstraint, JSON, DateTime, Boolean, Float, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200))
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Owned:
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    id: Mapped[str] = mapped_column(String(80), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Client(Owned, Base):
    __tablename__ = 'clients'
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(50), default='')
    currency: Mapped[str] = mapped_column(String(12), default='USD')
    note: Mapped[str] = mapped_column(String(5000), default='')
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    rates: Mapped[dict] = mapped_column(JSON, default=dict)
    commissions: Mapped[dict] = mapped_column(JSON, default=dict)


class Record(Owned, Base):
    __tablename__ = 'records'
    __table_args__ = (ForeignKeyConstraint(['user_id', 'client_id'], ['clients.user_id', 'clients.id'], ondelete='CASCADE'),)
    client_id: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(10))
    date: Mapped[str] = mapped_column(String(10))
    time: Mapped[str] = mapped_column(String(5))
    note: Mapped[str] = mapped_column(String(5000), default='')
    created_name: Mapped[str] = mapped_column(String(200), default='')
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(12))
    exchange_rate: Mapped[float] = mapped_column(Float)
    commission_type: Mapped[str] = mapped_column(String(30))
    commission_value: Mapped[float] = mapped_column(Float)
    commission_amount: Mapped[float] = mapped_column(Float)
    net_amount: Mapped[float] = mapped_column(Float)
    usd_equivalent: Mapped[float] = mapped_column(Float)
    signed_amount: Mapped[float] = mapped_column(Float)
    signed_usd: Mapped[float] = mapped_column(Float)
    commission_usd: Mapped[float] = mapped_column(Float)
    voided: Mapped[bool] = mapped_column(Boolean, default=False)


class Withdrawal(Owned, Base):
    __tablename__ = 'withdrawals'
    currency: Mapped[str] = mapped_column(String(12))
    amounts: Mapped[list] = mapped_column(JSON)
    count: Mapped[int] = mapped_column(Integer)
    total: Mapped[float] = mapped_column(Float)
    date: Mapped[str] = mapped_column(String(10))
    time: Mapped[str] = mapped_column(String(5))
    note: Mapped[str] = mapped_column(String(5000), default='')
    created_name: Mapped[str] = mapped_column(String(200), default='')
    voided: Mapped[bool] = mapped_column(Boolean, default=False)


class Settings(Owned, Base):
    __tablename__ = 'settings'
    shop_name: Mapped[str] = mapped_column(String(200), default='دفتري')
    shop_phone: Mapped[str] = mapped_column(String(50), default='')
    currencies: Mapped[list] = mapped_column(JSON)
    rates: Mapped[dict] = mapped_column(JSON)
    commissions: Mapped[dict] = mapped_column(JSON)


def camel(value):
    first, *rest = value.split('_')
    return first + ''.join(part.title() for part in rest)


def serialize(row):
    result = {}
    for col in row.__table__.columns:
        if col.name in ['user_id', 'password_hash', 'google_sub']:
            continue
        value = getattr(row, col.name)
        result[camel(col.name)] = value.isoformat() if isinstance(value, datetime) else value
    return result
