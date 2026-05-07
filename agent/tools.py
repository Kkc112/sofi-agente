# agent/tools.py — Herramientas del agente Sofi
# Generado por AgentKit

import os
import yaml
import logging
from datetime import datetime

logger = logging.getLogger("agentkit")


def cargar_info_negocio() -> dict:
    try:
        with open("config/business.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("config/business.yaml no encontrado")
        return {}


def obtener_horario() -> dict:
    info = cargar_info_negocio()
    hora_actual = datetime.now().hour
    dia_semana = datetime.now().weekday()  # 0=lunes, 6=domingo
    esta_abierto = (dia_semana < 5) and (8 <= hora_actual < 20)
    return {
        "horario": info.get("negocio", {}).get("horario", "Lunes a Viernes 08:00 a 20:00hs"),
        "esta_abierto": esta_abierto,
    }


def buscar_en_knowledge(consulta: str) -> str:
    """Busca información relevante en los archivos de /knowledge."""
    resultados = []
    knowledge_dir = "knowledge"

    if not os.path.exists(knowledge_dir):
        return "No hay archivos de conocimiento disponibles."

    for archivo in os.listdir(knowledge_dir):
        ruta = os.path.join(knowledge_dir, archivo)
        if archivo.startswith(".") or not os.path.isfile(ruta):
            continue
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read()
                if consulta.lower() in contenido.lower():
                    resultados.append(f"[{archivo}]: {contenido[:500]}")
        except (UnicodeDecodeError, IOError):
            continue

    if resultados:
        return "\n---\n".join(resultados)
    return "No encontré información específica sobre eso en mis archivos."


# ── Calificación de nuevos pacientes ────────────────────────

def registrar_paciente_nuevo(telefono: str, nombre: str, motivo: str, modalidad: str, cobertura: str) -> dict:
    """Registra los datos relevados durante la calificación inicial del paciente."""
    logger.info(f"Nuevo paciente calificado — {telefono}: {nombre} | Motivo: {motivo} | Modalidad: {modalidad} | Cobertura: {cobertura}")
    return {
        "telefono": telefono,
        "nombre": nombre,
        "motivo": motivo,
        "modalidad": modalidad,
        "cobertura": cobertura,
        "estado": "pendiente_turno",
    }


# ── Agenda de turnos ────────────────────────────────────────

def confirmar_turno(telefono: str, nombre: str, fecha: str, hora: str, modalidad: str) -> dict:
    """
    Registra un turno confirmado.
    En producción, aquí se integraría con Google Calendar API.
    """
    logger.info(f"Turno confirmado — {nombre} ({telefono}): {fecha} {hora} [{modalidad}]")
    return {
        "confirmado": True,
        "paciente": nombre,
        "fecha": fecha,
        "hora": hora,
        "modalidad": modalidad,
        "recordatorio": "Se enviará recordatorio 24hs y 1hs antes por WhatsApp",
    }


def cancelar_turno(telefono: str, motivo: str = "") -> dict:
    """Registra la cancelación de un turno."""
    logger.info(f"Turno cancelado — {telefono}. Motivo: {motivo}")
    return {
        "cancelado": True,
        "telefono": telefono,
        "mensaje": "Turno cancelado. Avisanos cuando quieras reagendar.",
    }
