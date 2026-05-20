# agent/brain.py — Cerebro del agente: máquina de 3 fases Demo Camaleón Universal

import os
import json
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


async def _extraer_datos_negocio(mensaje: str) -> dict | None:
    """
    Llama a Haiku para extraer niche, business_name y min_price del mensaje del usuario.
    Retorna un dict si se puede identificar al menos el niche. Nunca retorna None por
    falta de nombre: si el usuario no lo da, se genera uno por defecto.
    """
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "Extraé datos del mensaje de un dueño de negocio. "
                "Respondé SOLO con JSON válido, sin texto adicional ni bloques de código, con estas claves:\n"
                "- niche: el rubro o tipo de negocio (obligatorio si se menciona de cualquier forma)\n"
                "- business_name: el nombre comercial del negocio. "
                "  Si el usuario dice que no tiene nombre, que es nuevo, que no lo menciona, "
                "  o si simplemente no aparece en el mensaje, ponés null (NO uses el rubro como nombre).\n"
                "- min_price: precio, ticket o tarifa mencionada. Si no hay, null.\n"
                "El único campo REQUERIDO es niche. Si no podés identificar ningún rubro, retorná null.\n"
                'Ejemplo con nombre: {"niche": "peluquería", "business_name": "Cortes Express", "min_price": "$50"}\n'
                'Ejemplo sin nombre: {"niche": "hoteles", "business_name": null, "min_price": "100 usd"}'
            ),
            messages=[{"role": "user", "content": mensaje}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        datos = json.loads(raw)
        # Solo requerimos niche para avanzar
        if datos.get("niche"):
            return datos
        return None
    except Exception as e:
        logger.error(f"Error extrayendo datos del negocio: {e}")
        return None


async def procesar_mensaje(
    mensaje: str,
    historial: list[dict],
    sesion: SesionData,
) -> tuple[str, SesionData]:
    """
    Punto de entrada principal. Despacha según la fase actual.
    Retorna (respuesta_texto, sesion_actualizada).
    """
    prompts = _cargar_prompts()

    if sesion.fase == "ONBOARDING":
        return await _fase_onboarding(mensaje, historial, sesion, prompts)
    elif sesion.fase == "SIMULATION":
        return await _fase_simulation(mensaje, historial, sesion, prompts)
    else:
        return await _fase_pitch(sesion, prompts)


# ── Fase 1: ONBOARDING ───────────────────────────────────────────────────────

async def _fase_onboarding(
    mensaje: str,
    historial: list[dict],
    sesion: SesionData,
    prompts: dict,
) -> tuple[str, SesionData]:
    onb = prompts.get("onboarding", {})

    # Primer mensaje del usuario → devolver saludo y esperar datos
    if not historial:
        greeting = onb.get(
            "greeting",
            "¡Hola! Soy Sofi, la IA de demostración.\n\n"
            "Antes de mostrarte mis superpoderes, decime de forma directa: "
            "¿A qué nicho te dedicás, cómo se llama tu negocio y cuál es tu precio o ticket mínimo?",
        )
        return greeting, sesion

    # El usuario ya recibió el saludo — intentar extraer los datos del negocio
    datos = await _extraer_datos_negocio(mensaje)

    if datos and datos.get("niche"):
        niche = datos["niche"]
        # Si el usuario no dio nombre, se genera uno genérico antes de avanzar
        sesion.business_name = datos.get("business_name") or f"Negocio de {niche.capitalize()}"
        sesion.niche = niche
        sesion.min_price = datos.get("min_price") or "a convenir"
        sesion.fase = "SIMULATION"
        sesion.simulation_messages_count = 0

        activation = onb.get(
            "activation",
            "Espectacular.\n\n"
            "A partir de este preciso momento, me pongo la camiseta de {business_name}.\n\n"
            "Actuá como si fueras un cliente tuyo (curioso, molesto, corporativo) "
            "pidiendo info por WhatsApp y poneme a prueba. ¡Escribime!",
        )
        return activation.format(
            business_name=sesion.business_name,
            niche=sesion.niche,
            min_price=sesion.min_price,
        ), sesion

    # No se pudo extraer la info mínima — volver a pedir
    retry = onb.get(
        "retry",
        "Necesito tres datos concretos: el rubro de tu negocio, cómo se llama y cuál es tu precio o ticket mínimo. ¿Podés contarme eso?",
    )
    return retry, sesion


# ── Fase 2: SIMULATION ───────────────────────────────────────────────────────

async def _fase_simulation(
    mensaje: str,
    historial: list[dict],
    sesion: SesionData,
    prompts: dict,
) -> tuple[str, SesionData]:
    sesion.simulation_messages_count += 1

    # Al llegar al mensaje 3, cortar la simulación y pasar al pitch
    if sesion.simulation_messages_count >= 3:
        sesion.fase = "PITCH"
        return _construir_pitch(sesion, prompts)

    sim = prompts.get("simulation", {})
    system_template = sim.get("system_prompt", "")
    system_prompt = system_template.format(
        business_name=sesion.business_name or "el negocio",
        niche=sesion.niche or "servicios",
        min_price=sesion.min_price or "a convenir",
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
        respuesta = response.content[0].text
        logger.info(
            f"Simulation msg {sesion.simulation_messages_count}/3 "
            f"({response.usage.input_tokens} in / {response.usage.output_tokens} out)"
        )
        return respuesta, sesion
    except Exception as e:
        logger.error(f"Error en simulation: {e}")
        return prompts.get("error_message", "Problema técnico. Intentá de nuevo."), sesion


# ── Fase 3: PITCH ────────────────────────────────────────────────────────────

async def _fase_pitch(sesion: SesionData, prompts: dict) -> tuple[str, SesionData]:
    return _construir_pitch(sesion, prompts)


def _construir_pitch(sesion: SesionData, prompts: dict) -> tuple[str, SesionData]:
    template = prompts.get("pitch", {}).get(
        "message",
        "¡Alto ahí! Salgo de personaje.\n\n"
        "Como pudiste ver, acabo de perfilar al cliente, defendí tu precio mínimo de {min_price} "
        "y busqué cerrar la cita para {business_name} sin dar vueltas.\n\n"
        "Todo esto 24/7 en piloto automático.\n\n"
        "Si querés que instale a Sofi en tu WhatsApp comercial real esta semana, "
        "coordinemos una llamada de 15 min.\n\n"
        "¿Te queda mejor mañana a las 11:00 o a las 16:00?",
    )
    respuesta = template.format(
        business_name=sesion.business_name or "tu negocio",
        niche=sesion.niche or "tu sector",
        min_price=sesion.min_price or "tu precio mínimo",
    )
    return respuesta, sesion
