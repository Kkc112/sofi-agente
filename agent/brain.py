# agent/brain.py — Cerebro del agente: Sofi de Madero Event Solutions

import os
import yaml
import logging
from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from agent.memory import SesionData

load_dotenv()
logger = logging.getLogger("agentkit")

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _cargar_prompts() -> dict:
    try:
        with open("config/prompts.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error("config/prompts.yaml no encontrado")
        return {}


async def procesar_mensaje(
    mensaje: str,
    historial: list[dict],
    sesion: SesionData,
) -> tuple[str, SesionData]:
    """
    Punto de entrada principal.
    El flujo de onboarding/demo está desactivado — Sofi responde directamente
    como asistente de Madero Event Solutions en todas las fases.
    """
    prompts = _cargar_prompts()
    return await _responder_como_sofi(mensaje, historial, sesion, prompts)


async def _responder_como_sofi(
    mensaje: str,
    historial: list[dict],
    sesion: SesionData,
    prompts: dict,
) -> tuple[str, SesionData]:
    estancia = prompts.get("estancia_las_camelias", {})
    system_prompt = estancia.get(
        "system_prompt",
        "Eres Sofi, la asistente comercial de Madero Event Solutions. "
        "Tu objetivo es calificar al interesado y agendar una llamada con el equipo comercial.",
    )

    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial]
    mensajes.append({"role": "user", "content": mensaje})

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=system_prompt,
            messages=mensajes,
        )
        logger.info(
            f"Sofi respondió a {sesion.telefono} "
            f"({response.usage.input_tokens} in / {response.usage.output_tokens} out)"
        )
        return response.content[0].text, sesion
    except Exception as e:
        logger.error(f"Error generando respuesta: {e}")
        return prompts.get("error_message", "Problema técnico. Intentá de nuevo."), sesion
