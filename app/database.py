import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, DateTime, Integer, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import NullPool

from app.schemas import Profile

ROOT = Path(__file__).resolve().parent.parent


class Base(DeclarativeBase):
    pass


class ProfileRecord(Base):
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def make_engine(url: str | None = None):
    url = url or os.getenv("DATABASE_URL")
    hosted = os.getenv("RENDER") == "true"
    if hosted and not url:
        raise ValueError("Configurá DATABASE_URL con la conexión PostgreSQL de Neon antes de desplegar.")
    if not url:
        (ROOT / "data").mkdir(exist_ok=True)
        url = "sqlite:///" + (ROOT / "data" / "profile.db").as_posix()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    parsed = make_url(url)
    if hosted and parsed.get_backend_name() != "postgresql":
        raise ValueError("Render requiere PostgreSQL persistente; SQLite se reserva para desarrollo local.")
    if hosted and parsed.query.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise ValueError("La conexión PostgreSQL publicada debe incluir sslmode=require o verificación TLS más estricta.")
    if parsed.get_backend_name() == "postgresql":
        # Cerrar conexiones inactivas permite que Neon suspenda su cómputo.
        return create_engine(url, poolclass=NullPool, connect_args={"connect_timeout": 15})
    return create_engine(url, pool_pre_ping=True, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})


def read_profile(engine) -> Profile:
    with Session(engine) as session:
        record = session.get(ProfileRecord, 1)
        if record is None:
            raise LookupError("No hay perfil cargado.")
        return Profile.model_validate(record.content)


def save_profile(engine, profile: Profile) -> None:
    with Session(engine) as session, session.begin():
        record = session.get(ProfileRecord, 1)
        if record is None:
            record = ProfileRecord(id=1)
            session.add(record)
        record.content = profile.model_dump(mode="json")
        record.updated_at = datetime.now(timezone.utc)


def initialize(engine) -> None:
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        exists = session.get(ProfileRecord, 1) is not None
    if not exists:
        profile = Profile.model_validate_json((ROOT / "content" / "profile.json").read_text(encoding="utf-8"))
        save_profile(engine, profile)
