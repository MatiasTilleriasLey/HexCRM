from __future__ import annotations

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    company = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    proposals = db.relationship(
        "Proposal",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Client id={self.id} name={self.name!r}>"


class Proposal(db.Model):
    __tablename__ = "proposals"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer,
        db.ForeignKey("clients.id"),
        nullable=False,
    )
    title = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(300), nullable=True)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20),
        nullable=False,
        default="draft",  # draft, sent, accepted, rejected
    )
    objectives = db.Column(db.Text, nullable=True)
    scope_text = db.Column(db.Text, nullable=True)
    deliverables = db.Column(db.Text, nullable=True)
    tech_stack = db.Column(db.Text, nullable=True)
    work_plan = db.Column(db.Text, nullable=True)
    cost_breakdown = db.Column(db.Text, nullable=True)
    cost_items = db.Column(db.Text, nullable=True)  # JSON list of {"label": str, "amount": float}
    validity_days = db.Column(db.Integer, nullable=True)
    amount = db.Column(db.Float, nullable=True)
    currency = db.Column(db.String(10), nullable=True, default="CLP")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    client = db.relationship("Client", back_populates="proposals")
    def __repr__(self) -> str:
        return f"<Proposal id={self.id} client_id={self.client_id}>"

    @property
    def cost_items_list(self):
        try:
            import json

            data = json.loads(self.cost_items or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
