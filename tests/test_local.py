# tests/test_local.py — Simulador de chat en terminal (Lumio Event Solutions)

import asyncio
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.brain import procesar_mensaje
from agent.memory import (
    inicializar_db,
    guardar_mensaje,
    obtener_historial,
    obtener_sesion,
    guardar_sesion,
    limpiar_todo,
)

TELEFONO_TEST = "test-local-001"

AYUDA = """
  Comandos especiales:
    'reset'    — reinicia sesión e historial
    'estado'   — muestra el estado actual de la sesión
    'salir'    — termina el test
"""


def _mostrar_sesion(sesion):
    print(f"\n  Fase:        {sesion.fase}")
    print(f"  Negocio:     {sesion.business_name or '—'}")
    print()


async def main():
    await inicializar_db()

    print()
    print("=" * 60)
    print("   Sofi — Lumio Event Solutions")
    print("   Asistente comercial y appointment setter")
    print("=" * 60)
    print(AYUDA)
    print("-" * 60)
    print()

    # Saludo inicial si la conversación arranca desde cero
    historial_inicial = await obtener_historial(TELEFONO_TEST)
    if not historial_inicial:
        saludo = (
            "Hola, soy Sofi de Lumio Event Solutions.\n\n"
            "Te ayudo a orientar tu evento, entender el alcance y coordinar una llamada breve "
            "con el equipo comercial. ¿Qué tipo de evento estás organizando?"
        )
        print(f"Sofi: {saludo}\n")
        sesion_inicial = await obtener_sesion(TELEFONO_TEST)
        await guardar_mensaje(TELEFONO_TEST, "assistant", saludo)
        await guardar_sesion(sesion_inicial)

    while True:
        try:
            mensaje = input("Vos: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nTest finalizado.")
            break

        if not mensaje:
            continue

        if mensaje.lower() == "salir":
            print("\nTest finalizado.")
            break

        if mensaje.lower() == "reset":
            await limpiar_todo(TELEFONO_TEST)
            saludo = (
                "Hola, soy Sofi de Lumio Event Solutions.\n\n"
                "Te ayudo a orientar tu evento, entender el alcance y coordinar una llamada breve "
                "con el equipo comercial. ¿Qué tipo de evento estás organizando?"
            )
            print(f"\nSofi: {saludo}\n")
            sesion_nueva = await obtener_sesion(TELEFONO_TEST)
            await guardar_mensaje(TELEFONO_TEST, "assistant", saludo)
            await guardar_sesion(sesion_nueva)
            continue

        if mensaje.lower() == "estado":
            sesion = await obtener_sesion(TELEFONO_TEST)
            _mostrar_sesion(sesion)
            continue

        sesion = await obtener_sesion(TELEFONO_TEST)
        historial = await obtener_historial(TELEFONO_TEST)

        print("\nSofi: ", end="", flush=True)
        respuesta, sesion_actualizada = await procesar_mensaje(mensaje, historial, sesion)
        print(respuesta)
        print()

        await guardar_mensaje(TELEFONO_TEST, "user", mensaje)
        await guardar_mensaje(TELEFONO_TEST, "assistant", respuesta)
        await guardar_sesion(sesion_actualizada)


if __name__ == "__main__":
    asyncio.run(main())
