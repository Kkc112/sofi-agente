# tests/test_local.py — Simulador de chat en terminal (Demo Camaleón Universal, 3 fases)

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

FASES_LABEL = {
    "ONBOARDING": "Fase 1 — ONBOARDING  (recolectando datos del negocio)",
    "SIMULATION": "Fase 2 — SIMULATION  (setter Hormozi activo)",
    "PITCH":      "Fase 3 — PITCH       (cierre B2B)",
}

AYUDA = """
  Comandos especiales:
    'reset'    — reinicia sesión + historial (vuelve a Fase 1)
    'estado'   — muestra el estado actual de la sesión
    'salir'    — termina el test
"""


def _mostrar_sesion(sesion):
    print(f"\n  Fase:        {sesion.fase}")
    print(f"  Negocio:     {sesion.business_name or '—'}")
    print(f"  Nicho:       {sesion.niche or '—'}")
    print(f"  Precio mín:  {sesion.min_price or '—'}")
    print(f"  Msgs sim:    {sesion.simulation_messages_count}/3\n")


async def main():
    await inicializar_db()

    print()
    print("=" * 60)
    print("   Demo Camaleón Universal — Test Local")
    print("   Sistema de 3 Fases (Hormozi Edition)")
    print("=" * 60)
    print(AYUDA)
    print("  Flujo esperado:")
    print("  1. Bot pide datos del negocio")
    print("  2. Vos respondés con nicho, nombre y precio")
    print("  3. Simulación de 3 mensajes como cliente")
    print("  4. Pitch de cierre automático")
    print()
    print("-" * 60)
    print()

    while True:
        sesion = await obtener_sesion(TELEFONO_TEST)
        fase_label = FASES_LABEL.get(sesion.fase, sesion.fase)
        print(f"[{fase_label}]")

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
            print("\n  [Sesión y historial reiniciados — volvés a Fase 1]\n")
            continue

        if mensaje.lower() == "estado":
            _mostrar_sesion(sesion)
            continue

        historial = await obtener_historial(TELEFONO_TEST)

        print("\nSofi: ", end="", flush=True)
        respuesta, sesion_actualizada = await procesar_mensaje(mensaje, historial, sesion)
        print(respuesta)
        print()

        await guardar_mensaje(TELEFONO_TEST, "user", mensaje)
        await guardar_mensaje(TELEFONO_TEST, "assistant", respuesta)
        await guardar_sesion(sesion_actualizada)

        # Indicar si hubo transición de fase
        if sesion_actualizada.fase != sesion.fase:
            print(f"  >>> Transición: {sesion.fase} → {sesion_actualizada.fase}\n")


if __name__ == "__main__":
    asyncio.run(main())
