# agent/main.py — Servidor FastAPI + Webhook de WhatsApp (Demo Camaleón Universal)

import io
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv
import httpx
from openai import AsyncOpenAI

from agent.brain import procesar_mensaje
from agent.memory import (
    inicializar_db,
    guardar_mensaje,
    obtener_historial,
    obtener_sesion,
    guardar_sesion,
    limpiar_todo,
)
from agent.providers import obtener_proveedor

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def transcribir_audio(audio_url: str) -> str | None:
    """
    Descarga un audio de Twilio y lo transcribe con OpenAI Whisper.
    Retorna el texto transcripto, o None si algo falla.
    """
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    try:
        async with httpx.AsyncClient(timeout=30) as http:
            r = await http.get(audio_url, auth=(account_sid, auth_token))
            r.raise_for_status()

        # Determinar extensión según Content-Type para que Whisper reconozca el formato
        content_type = r.headers.get("content-type", "audio/ogg")
        if "ogg" in content_type:
            ext = "ogg"
        elif "amr" in content_type:
            ext = "amr"
        elif "mp4" in content_type or "m4a" in content_type:
            ext = "mp4"
        elif "mpeg" in content_type or "mp3" in content_type:
            ext = "mp3"
        else:
            ext = "ogg"

        audio_bytes = io.BytesIO(r.content)
        audio_bytes.name = f"audio.{ext}"

        transcripcion = await openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_bytes,
            language="es",
        )
        texto = transcripcion.text.strip()
        logger.info(f"Audio transcripto: {texto[:100]}")
        return texto if texto else None

    except Exception as e:
        logger.error(f"Error transcribiendo audio: {e}")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inicializar_db()
    logger.info("Base de datos inicializada")
    logger.info(f"Servidor AgentKit corriendo en puerto {PORT}")
    logger.info(f"Proveedor de WhatsApp: {proveedor.__class__.__name__}")
    yield


app = FastAPI(
    title="AgentKit — Demo Camaleón Universal",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def health_check():
    return {"status": "ok", "service": "agentkit", "version": "2.0.0"}


@app.get("/webhook")
async def webhook_verificacion(request: Request):
    resultado = await proveedor.validar_webhook(request)
    if resultado is not None:
        return PlainTextResponse(str(resultado))
    return {"status": "ok"}


@app.post("/webhook")
async def webhook_handler(request: Request):
    try:
        mensajes = await proveedor.parsear_webhook(request)

        for msg in mensajes:
            if msg.es_propio:
                continue

            # Si es audio, transcribirlo antes de seguir
            if msg.audio_url:
                transcripcion = await transcribir_audio(msg.audio_url)
                if not transcripcion:
                    await proveedor.enviar_mensaje(
                        msg.telefono,
                        "No pude escuchar el audio. ¿Podés escribirme lo que necesitás?",
                    )
                    continue
                msg.texto = transcripcion
                logger.info(f"Audio de {msg.telefono} → '{msg.texto[:80]}'")

            if not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

            # Comando de reinicio: borra sesión e historial completos
            if msg.texto.strip().lower() in ("reiniciar", "reset"):
                await limpiar_todo(msg.telefono)
                respuesta = (
                    "Listo, empezamos de cero.\n\n"
                    "¡Hola! Soy Sofi, la IA de demostración.\n\n"
                    "Sé que sos dueño de un negocio, empresa o profesional independiente "
                    "que busca escalar su facturación y automatizar sus ventas por WhatsApp.\n\n"
                    "Antes de mostrarte mis capacidades, decime de forma directa: "
                    "¿A qué nicho te dedicás, cómo se llama tu negocio y cuál es tu precio o ticket mínimo?"
                )
                await proveedor.enviar_mensaje(msg.telefono, respuesta)
                logger.info(f"Sesión reiniciada para {msg.telefono}")
                continue

            # Obtener historial y estado de sesión ANTES de guardar el mensaje actual
            historial = await obtener_historial(msg.telefono)
            sesion = await obtener_sesion(msg.telefono)

            logger.debug(f"Fase actual de {msg.telefono}: {sesion.fase}")

            # Procesar mensaje según la fase (brain maneja la máquina de estados)
            respuesta, sesion_actualizada = await procesar_mensaje(
                msg.texto, historial, sesion
            )

            # Persistir mensaje del usuario, respuesta y estado actualizado
            await guardar_mensaje(msg.telefono, "user", msg.texto)
            await guardar_mensaje(msg.telefono, "assistant", respuesta)
            await guardar_sesion(sesion_actualizada)

            # Enviar respuesta por WhatsApp
            await proveedor.enviar_mensaje(msg.telefono, respuesta)

            logger.info(f"[{sesion_actualizada.fase}] Respuesta a {msg.telefono}: {respuesta[:80]}...")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error en webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agent.main:app", host="0.0.0.0", port=8080, reload=False)
