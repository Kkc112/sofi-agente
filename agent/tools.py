# agent/tools.py — Herramientas auxiliares del agente Sofi
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
        "horario": info.get("negocio", {}).get("horario", "Consultas por WhatsApp"),
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


def registrar_lead_evento(
    telefono: str,
    tipo_evento: str,
    fecha: str = "",
    ciudad: str = "",
    asistentes: str = "",
    servicios: str = "",
) -> dict:
    """Registra datos básicos relevados durante la calificación comercial."""
    logger.info(
        "Lead de evento calificado — %s: %s | %s | %s | %s | %s",
        telefono,
        tipo_evento,
        fecha,
        ciudad,
        asistentes,
        servicios,
    )
    return {
        "telefono": telefono,
        "tipo_evento": tipo_evento,
        "fecha": fecha,
        "ciudad": ciudad,
        "asistentes": asistentes,
        "servicios": servicios,
        "estado": "pendiente_llamada",
    }


def registrar_llamada_comercial(telefono: str, fecha: str, hora: str) -> dict:
    """
    Registra una llamada comercial coordinada.
    En producción, aquí se integraría con calendario o CRM.
    """
    logger.info("Llamada comercial coordinada — %s: %s %s", telefono, fecha, hora)
    return {
        "coordinada": True,
        "telefono": telefono,
        "fecha": fecha,
        "hora": hora,
        "mensaje": "Llamada comercial coordinada.",
    }
