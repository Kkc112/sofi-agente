# agent/main.py — Servidor FastAPI + Webhook de WhatsApp (Demo Camaleón Universal)

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent.brain import procesar_mensaje
from agent.memory import (
    inicializar_db,
    guardar_mensaje,
    obtener_historial,
    obtener_sesion,
    guardar_sesion,
)
from agent.providers import obtener_proveedor

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
log_level = logging.DEBUG if ENVIRONMENT == "development" else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger("agentkit")

proveedor = obtener_proveedor()
PORT = int(os.getenv("PORT", 8000))


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
            if msg.es_propio or not msg.texto:
                continue

            logger.info(f"Mensaje de {msg.telefono}: {msg.texto}")

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
