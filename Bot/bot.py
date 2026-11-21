#!/usr/bin/env python3
"""Michi Novato: bot de ejemplo de dificultad FACIL para pokerFight.

Juega con una lista de reglas escritas con if (ver estrategia.py). No usa
ninguna libreria fuera de la estandar de Python, asi que corre en cualquier
maquina con Python 3.8 o superior.

Uso (lo mismo que hace la arena cuando lo lanza):

    python bots/novato/bot.py -addr localhost:9000 -token mi-token

Archivos:
    bot.py         este archivo: el bucle de mensajes con la mesa.
    conexion.py    socket, saludo y JSON Lines. Cópialo tal cual a tu bot.
    turno.py       ayudantes para calcular apuestas validas.
    cartas.py      lectura de la mano con conteos.
    estrategia.py  LA ESTRATEGIA. Es lo que tienes que cambiar.
"""

import argparse
import sys

from cartas import texto_cartas
from conexion import Conexion, MesaRechazo, log
from estrategia import decidir
from memoria_rivales import MemoriaRivales
from turno import Turno

NOMBRE = "Michi Novato"

# Cuantas veces se intenta volver si se corta la conexion a mitad de partida.
# Mientras el bot no esta, la mesa juega por el (check o fold) y le anota un
# timeout, asi que conviene volver rapido.
REINTENTOS_RECONEXION = 5


def describir_accion(accion):
    if "monto" in accion:
        return f"{accion['tipo']} {accion['monto']}"
    return accion["tipo"]


def _formatear_fichas(cantidad):
    return f"{cantidad:,}".replace(",", ".")


def registrar_estado_publico(estado, mi_id, indice_acciones, eliminados):
    jugadores = estado.get("jugadores") or []
    nombres = {
        jugador.get("id"): jugador.get("nombre", jugador.get("id", "rival"))
        for jugador in jugadores
    }
    acciones = estado.get("historial_acciones") or []
    if indice_acciones > len(acciones):
        indice_acciones = 0

    for registro in acciones[indice_acciones:]:
        id_jugador = registro.get("id_jugador")
        if id_jugador in (None, mi_id):
            continue
        accion = registro.get("accion") or {}
        tipo = accion.get("tipo", "acción")
        detalle = f" {accion['monto']}" if "monto" in accion else ""
        nombre = nombres.get(id_jugador, id_jugador)
        log(f"  [{registro.get('etapa', '?')}] {nombre}: {tipo}{detalle}")

    eliminados_nuevos = []
    lineas_fichas = []
    for jugador in jugadores:
        id_jugador = jugador.get("id")
        nombre = nombres.get(id_jugador, "jugador")
        if jugador.get("en_torneo") is False and id_jugador not in eliminados:
            eliminados.add(id_jugador)
            eliminados_nuevos.append(nombre)

        estados = []
        if jugador.get("allin"):
            estados.append("ALL-IN")
        if jugador.get("en_torneo") is False:
            estados.append("ELIMINADO")
        etiqueta = f" [{', '.join(estados)}]" if estados else ""
        saldo = _formatear_fichas(jugador.get("saldo", 0))
        apuesta = _formatear_fichas(jugador.get("apuesta_ronda", 0))
        lineas_fichas.append(
            f"{nombre}: saldo {saldo}, apuesta {apuesta}{etiqueta}"
        )

    if lineas_fichas:
        log("  Fichas: " + " | ".join(lineas_fichas))
    for nombre in eliminados_nuevos:
        log(
            f"  {nombre} agotó sus fichas. "
            f"Eliminaciones observadas: {len(eliminados)}"
        )
    return len(acciones)


def jugar(conexion, silencioso, memoria=None):
    """Atiende mensajes hasta que la mesa cierre. Devuelve True si la partida
    termino normalmente, False si se corto la conexion."""
    if memoria is None:
        memoria = MemoriaRivales()
    mano = []
    acciones_reportadas = 0
    eliminados = set()
    while True:
        try:
            mensaje = conexion.recibir()
        except OSError:
            return False
        if mensaje is None:
            return True

        tipo = mensaje.get("tipo")

        if tipo == "mano_inicio":
            mano = mensaje.get("cartas") or []
            memoria.nueva_mano()
            acciones_reportadas = 0

        elif tipo == "solicitar_accion":
            turno = Turno(conexion, mensaje, mano)
            memoria.observar_estado(turno.estado, conexion.id_jugador)
            if not silencioso:
                acciones_reportadas = registrar_estado_publico(
                    turno.estado, conexion.id_jugador, acciones_reportadas, eliminados
                )
            accion, motivo = decidir(turno, memoria)
            try:
                conexion.responder(turno.estado, accion)
            except OSError:
                return False
            if not silencioso:
                log(f"[{turno.etapa:7}] {texto_cartas(mano)} | mesa {texto_cartas(turno.comunitarias)}"
                    f" | {describir_accion(accion):12} | {motivo}")

        elif tipo == "mano_fin":
            # Informativo. Si hubo showdown, resultado["mostradas"] trae las
            # cartas del rival: es lo unico legitimo para aprender de el.
            resultado = mensaje.get("resultado") or {}
            memoria.observar_resultado(resultado, conexion.id_jugador)
            for reparto in resultado.get("repartos", []):
                if reparto.get("id_jugador") == conexion.id_jugador and not silencioso:
                    log(f"           gane {reparto.get('monto', 0)} fichas")

        elif tipo == "estado":
            estado = mensaje.get("estado")
            if estado:
                memoria.observar_estado(estado, conexion.id_jugador)
                if not silencioso:
                    acciones_reportadas = registrar_estado_publico(
                        estado, conexion.id_jugador, acciones_reportadas, eliminados
                    )

        elif tipo == "error":
            log(f"la mesa aviso un error: {mensaje.get('mensaje', '')}")

        # "estado" es una actualizacion tras la accion de otro: no se responde.


def main():
    parser = argparse.ArgumentParser(description=f"{NOMBRE}: bot facil de pokerFight")
    parser.add_argument("-addr", default="localhost:9000", help="direccion de la mesa (host:puerto)")
    parser.add_argument("-token", default="michi-novato", help="token de sesion")
    parser.add_argument("-silencioso", action="store_true", help="no imprime cada decision")
    argumentos = parser.parse_args()

    conexion = Conexion(argumentos.addr, argumentos.token)
    try:
        conexion.conectar()
    except (MesaRechazo, ConnectionError) as error:
        log(f"{NOMBRE}: {error}")
        sys.exit(1)
    log(f"{NOMBRE} conectado como {conexion.id_jugador} en la silla {conexion.silla}")

    memoria = MemoriaRivales()
    for intento in range(REINTENTOS_RECONEXION + 1):
        if jugar(conexion, argumentos.silencioso, memoria):
            log(f"{NOMBRE}: la mesa cerro la partida")
            return
        if intento == REINTENTOS_RECONEXION:
            break
        # Se volvio a conectar con el MISMO token: la mesa reconoce al bot y
        # le devuelve su silla y su saldo.
        log(f"{NOMBRE}: se corto la conexion, reintentando ({intento + 1}/{REINTENTOS_RECONEXION})")
        conexion.cerrar()
        try:
            conexion.conectar(intentos=10, espera_s=0.5)
        except (MesaRechazo, ConnectionError) as error:
            log(f"{NOMBRE}: no se pudo volver: {error}")
            break
    sys.exit(1)


if __name__ == "__main__":
    main()
