# agent/memory.py — Memoria de conversaciones + estado de sesión con SQLite

import os
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, select
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── Modelo de mensajes (historial de conversación) ───────────────────────────

class Mensaje(Base):
    __tablename__ = "mensajes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono: Mapped[str] = mapped_column(String(50), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Modelo de estado de sesión (Demo Camaleón) ───────────────────────────────

@dataclass
class SesionData:
    """Estado de la sesión del usuario por número de teléfono."""
    telefono: str
    fase: str = "SIMULATION"
    business_name: str | None = None
    min_price: str | None = None
    niche: str | None = None
    simulation_messages_count: int = 0


class SesionUsuario(Base):
    __tablename__ = "sesiones"

    telefono: Mapped[str] = mapped_column(String(50), primary_key=True)
    fase: Mapped[str] = mapped_column(String(20), default="SIMULATION")
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    min_price: Mapped[str | None] = mapped_column(String(100), nullable=True)
    niche: Mapped[str | None] = mapped_column(String(200), nullable=True)
    simulation_messages_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Funciones de base de datos ───────────────────────────────────────────────

async def inicializar_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def guardar_mensaje(telefono: str, role: str, content: str):
    async with async_session() as session:
        mensaje = Mensaje(
            telefono=telefono,
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
        )
        session.add(mensaje)
        await session.commit()


async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    async with async_session() as session:
        query = (
            select(Mensaje)
            .where(Mensaje.telefono == telefono)
            .order_by(Mensaje.timestamp.desc())
            .limit(limite)
        )
        result = await session.execute(query)
        mensajes = result.scalars().all()
        mensajes.reverse()
        return [{"role": m.role, "content": m.content} for m in mensajes]


async def obtener_sesion(telefono: str) -> SesionData:
    async with async_session() as session:
        row = await session.get(SesionUsuario, telefono)
        if row is None:
            return SesionData(
                telefono=telefono,
                fase="SIMULATION",
                business_name="Madero Event Solutions",
                niche="eventos integrales",
                min_price="A medida segun alcance",
            )
        return SesionData(
            telefono=row.telefono,
            fase=row.fase,
            business_name=row.business_name,
            min_price=row.min_price,
            niche=row.niche,
            simulation_messages_count=row.simulation_messages_count,
        )


async def guardar_sesion(sesion: SesionData) -> None:
    async with async_session() as session:
        row = await session.get(SesionUsuario, sesion.telefono)
        if row is None:
            row = SesionUsuario(telefono=sesion.telefono)
            session.add(row)
        row.fase = sesion.fase
        row.business_name = sesion.business_name
        row.min_price = sesion.min_price
        row.niche = sesion.niche
        row.simulation_messages_count = sesion.simulation_messages_count
        row.updated_at = datetime.utcnow()
        await session.commit()


async def limpiar_historial(telefono: str):
    async with async_session() as session:
        query = select(Mensaje).where(Mensaje.telefono == telefono)
        result = await session.execute(query)
        for msg in result.scalars().all():
            await session.delete(msg)
        await session.commit()


async def limpiar_sesion(telefono: str):
    async with async_session() as session:
        row = await session.get(SesionUsuario, telefono)
        if row:
            await session.delete(row)
            await session.commit()


async def limpiar_todo(telefono: str):
    """Borra historial + estado de sesión. Útil para reiniciar el flujo completo."""
    await limpiar_historial(telefono)
    await limpiar_sesion(telefono)
