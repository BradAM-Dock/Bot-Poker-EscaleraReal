"""Estrategia de Michi Novato: reglas preflop y equidad Monte Carlo postflop.

La estrategia preflop usa reglas y despues del flop estima la equidad contra
rangos aleatorios ponderados por las acciones observadas.

decidir() devuelve la accion y un motivo en texto, que se imprime en los logs
para que puedas seguir lo que piensa el bot mano a mano.

Ideas de poker que usa (todas explicadas donde aparecen):
  - Tabla de manos iniciales: con que dos cartas vale la pena entrar.
  - Simulaciones Monte Carlo para estimar la fraccion esperada del pozo.
  - Pot odds y cantidad de rivales al decidir si pagar o apostar.
"""

import random

from cartas import grupo_preflop
from equidad import estimar_equidad

_ACCIONES_MINIMAS_AGRESOR = 12
_FRECUENCIA_MINIMA_AGRESION = 0.35
_SHOWDOWNS_MINIMOS_CONFIABLES = 3
_FRECUENCIA_FUERTE_MAXIMA = 0.55
_PRECIO_MAXIMO_CALL_ADAPTATIVO = 22
_PROBABILIDAD_CBET_SECA = 0.65
_STACK_PROFUNDO_BB = 100
_CALL_3BET_MAXIMO_BB = 10
_STACK_MINIMO_POSTFLOP_BB = 20


def decidir(turno, memoria=None):
    if len(turno.comunitarias) < 3:
        return preflop(turno, memoria)
    return postflop(turno, memoria)


# --- Antes del flop -------------------------------------------------------------

def preflop(t, memoria=None):
    grupo = grupo_preflop(t.mano)
    cg = t.ciega_grande
    # Si la apuesta mas alta es la ciega grande, nadie subio todavia.
    nadie_subio = t.apuesta_actual <= cg

    if grupo == "premium":
        if nadie_subio:
            return _apostar_preflop(t, 3 * cg, "premium: abro a 3 ciegas")
        agresor = _ultimo_agresor_preflop(t)
        if (agresor is not None
                and _mano_paga_3bet(t, agresor[0])
                and _puede_pagar_3bet(t)):
            return t.pagar(), "JJ/AQ: pago la 3-bet sin comprometer todo el stack"
        if _subida_premium_seria_allin(t):
            if (agresor is not None
                    and _allin_preflop_permitido(t, agresor[0])
                    and t.puede("allin")):
                return t.todo(), "premium seleccionado por stack efectivo: all-in"
            return t.pasar_o_retirarse(), "premium: no convierto esta subida en all-in"
        return _apostar_preflop(
            t, 3 * t.apuesta_actual, "premium: resubo al triple"
        )

    if grupo == "fuerte":
        if nadie_subio:
            return _apostar_preflop(t, 3 * cg, "fuerte: abro a 3 ciegas")
        if t.por_igualar <= 4 * cg:
            return t.pagar(), "fuerte: pago una subida normal"
        agresor = _ultimo_agresor_preflop(t)
        if (agresor is not None and _es_aq(t.mano)
                and _puede_pagar_3bet(t)):
            return t.pagar(), "AQ: pago la 3-bet sin comprometer todo el stack"
        perfil = _perfil_agresor_frecuente_preflop(t, memoria)
        costo = min(t.por_igualar, max(0, t.yo.get("saldo", 0)))
        precio = costo * 100 / (t.pozo + costo) if t.pozo + costo else 100
        if (perfil is not None and t.rivales_en_mano <= 2
                and precio <= _PRECIO_MAXIMO_CALL_ADAPTATIVO):
            return t.pagar(), (
                f"fuerte: pago con precio {precio:.0f}% ante agresor frecuente "
                "sin evidencia fuerte"
            )
        return t.pasar_o_retirarse(), "fuerte, pero la subida es enorme"

    if grupo == "jugable":
        if nadie_subio and t.hablo_ultimo:
            # En el boton, si nadie entro, subir roba las ciegas seguido.
            return _apostar_preflop(
                t, 3 * cg, "jugable en buena posicion: intento robar las ciegas"
            )
        if t.por_igualar <= cg:
            return t.pagar(), "jugable: entro barato"
        return t.pasar_o_retirarse(), "jugable, pero no vale tanto"

    if grupo == "especulativa":
        # Las conectoras del mismo palo ganan pozos grandes cuando ligan, y
        # para eso tiene que haber gente en el pozo. Solo entramos baratas.
        if t.por_igualar <= cg and t.rivales_en_mano >= 2:
            return t.pagar(), "especulativa: entro barato con varios rivales"
        return t.pasar_o_retirarse(), "especulativa: no paga la entrada"

    return t.pasar_o_retirarse(), "basura: me voy (o paso si es gratis)"


def _ultimo_agresor_preflop(t):
    for registro in reversed(t.estado.get("historial_acciones", [])):
        accion = registro.get("accion") or {}
        if (registro.get("etapa") == "preflop"
                and accion.get("tipo") in ("bet", "raise", "allin")):
            return registro.get("id_jugador"), accion["tipo"]
    return None


def _cantidad_agresiones_preflop(t):
    return sum(
        registro.get("etapa") == "preflop"
        and (registro.get("accion") or {}).get("tipo") in ("bet", "raise", "allin")
        for registro in t.estado.get("historial_acciones", [])
    )


def _es_pareja(mano, rango):
    return len(mano) == 2 and mano[0]["rango"] == rango and mano[1]["rango"] == rango


def _es_aq(mano):
    return (len(mano) == 2
            and {carta["rango"] for carta in mano} == {12, 14})


def _es_aks(mano):
    return (len(mano) == 2
            and {carta["rango"] for carta in mano} == {13, 14}
            and mano[0]["palo"] == mano[1]["palo"])


def _subida_premium_seria_allin(t):
    return max(3 * t.apuesta_actual, t.subida_minima) >= t.techo


def _apostar_preflop(t, monto, motivo):
    if max(monto, t.subida_minima) >= t.techo:
        agresor = _ultimo_agresor_preflop(t)
        agresor_id = agresor[0] if agresor is not None else None
        if not _allin_preflop_permitido(t, agresor_id):
            return t.pasar_o_retirarse(), "evito un all-in preflop fuera del rango"
    return t.apostar(monto), motivo


def _stack_efectivo_preflop(t, agresor_id):
    mi_stack = max(0, t.yo.get("saldo", 0) + t.yo.get("apuesta_ronda", 0))
    if agresor_id is None:
        return mi_stack
    for jugador in t.estado.get("jugadores", []):
        if jugador.get("id") == agresor_id:
            stack_rival = max(
                0, jugador.get("saldo", 0) + jugador.get("apuesta_ronda", 0)
            )
            return min(mi_stack, stack_rival)
    return mi_stack


def _allin_preflop_permitido(t, agresor_id):
    rangos = {carta["rango"] for carta in t.mano}
    es_pareja = len(t.mano) == 2 and len(rangos) == 1
    stack_efectivo_bb = _stack_efectivo_preflop(t, agresor_id) / t.ciega_grande
    if stack_efectivo_bb > _STACK_PROFUNDO_BB:
        return es_pareja and next(iter(rangos)) >= 13
    return (
        (es_pareja and next(iter(rangos)) >= 12)
        or _es_aks(t.mano)
    )


def _mano_paga_3bet(t, agresor_id):
    if _es_pareja(t.mano, 11) or _es_aq(t.mano):
        return True
    stack_efectivo_bb = _stack_efectivo_preflop(t, agresor_id) / t.ciega_grande
    return (
        stack_efectivo_bb > _STACK_PROFUNDO_BB
        and (_es_pareja(t.mano, 12) or _es_aks(t.mano))
    )


def _puede_pagar_3bet(t):
    agresor = _ultimo_agresor_preflop(t)
    saldo = max(0, t.yo.get("saldo", 0))
    costo = t.por_igualar
    if (agresor is None or agresor[0] == t.mi_id or agresor[1] == "allin"
            or _cantidad_agresiones_preflop(t) < 2
            or t.rivales_en_mano != 1
            or not t.puede("call")
            or costo <= 0
            or costo >= saldo
            or costo > _CALL_3BET_MAXIMO_BB * t.ciega_grande
            or saldo - costo < _STACK_MINIMO_POSTFLOP_BB * t.ciega_grande):
        return False

    return not any(
        jugador.get("id") == agresor[0] and jugador.get("allin")
        for jugador in t.estado.get("jugadores", [])
    )


def _perfil_agresor_frecuente_preflop(t, memoria):
    if memoria is None:
        return None

    ultimo_agresor = _ultimo_agresor_preflop(t)
    if ultimo_agresor is None or ultimo_agresor[0] in (None, t.mi_id):
        return None

    perfil = memoria.perfil(ultimo_agresor[0])
    tendencias = perfil or {}
    acciones = tendencias.get("acciones_por_etapa", {}).get("preflop", 0)
    agresion = tendencias.get("frecuencia_agresion", {}).get("preflop", 0.5)
    if acciones < _ACCIONES_MINIMAS_AGRESOR or agresion < _FRECUENCIA_MINIMA_AGRESION:
        return None

    muestras_por_accion = tendencias.get("showdowns_por_accion")
    if muestras_por_accion is not None:
        muestra = (
            muestras_por_accion.get("preflop", {})
            .get(ultimo_agresor[1])
        )
        mostradas = muestra.get("muestras", 0) if muestra else 0
        frecuencia_fuerte = muestra.get("frecuencia_fuerte", 0.5) if muestra else 0.5
    else:
        mostradas = tendencias.get("agresiones_mostradas", 0)
        frecuencia_fuerte = tendencias.get(
            "frecuencia_fuerte_en_agresiones_mostradas", 0.5
        )
    if (mostradas >= _SHOWDOWNS_MINIMOS_CONFIABLES
            and frecuencia_fuerte > _FRECUENCIA_FUERTE_MAXIMA):
        return None
    return perfil


# --- Despues del flop -------------------------------------------------------------

def postflop(t, memoria=None):
    equidad = estimar_equidad(
        t.mano,
        t.comunitarias,
        t.rivales_en_mano,
        timeout_ms=t.timeout_ms,
        perfiles_rivales=perfiles_accion_rivales(t, memoria),
    )
    rivales = t.rivales_en_mano

    if t.por_igualar == 0:
        umbral_apuesta = min(0.82, 0.62 + 0.04 * max(0, rivales - 1))
        if (_puede_hacer_cbet_seca(t)
                and _azar_cbet(t) < _PROBABILIDAD_CBET_SECA):
            return t.apostar_pozo(1 / 3), (
                "c-bet 33%: fui el último agresor preflop, heads-up y flop seco"
            )
        if equidad >= umbral_apuesta and t.puede("bet"):
            return t.apostar_pozo(0.5), (
                f"equidad {equidad:.0%} contra {rivales} rival(es): apuesta por valor"
            )
        if (t.etapa == "river" and rivales == 1 and t.hablo_ultimo
                and t.subidas_en_esta_calle == 0):
            return t.apostar_pozo(0.5), (
                f"equidad {equidad:.0%}: farol en river tras check del rival"
            )
        return t.pasar_o_retirarse(), f"equidad {equidad:.0%}: paso"

    margen = 0.04 + min(0.015 * max(0, rivales - 1), 0.06)
    costo = min(t.por_igualar, max(0, t.yo.get("saldo", 0)))
    hay_rival_allin = any(
        jugador.get("id") != t.mi_id
        and jugador.get("activo")
        and jugador.get("en_mano", True)
        and jugador.get("allin")
        for jugador in t.estado.get("jugadores", [])
    )
    if not hay_rival_allin and costo > 0 and (
        costo == t.por_igualar or rivales == 1
    ):
        pozo_antes_de_pagar = t.pozo
        if costo < t.por_igualar:
            # Heads-up, el exceso que el rival no puede cobrar se le devuelve.
            pozo_antes_de_pagar -= t.por_igualar - costo
        pozo_si_paga = pozo_antes_de_pagar + costo
        ev = valor_esperado_pagar(equidad, pozo_antes_de_pagar, costo)
        margen_ev = margen * pozo_si_paga
        paga = ev >= margen_ev
        detalle_pago = f"EV {ev:.1f} fichas; margen requerido {margen_ev:.1f}"
    else:
        # La equidad actual no separa los sub-pozos en mesas multiway.
        precio = t.porcentaje_para_pagar / 100
        paga = equidad >= precio + margen
        detalle_pago = (
            f"equidad {equidad:.0%} vs precio {precio:.0%} "
            f"+ margen {margen:.0%} (pozo lateral/all-in)"
        )

    if paga:
        umbral_subida = min(0.91, 0.84 + 0.03 * max(0, rivales - 1))
        if equidad >= umbral_subida and t.puede("raise"):
            return t.apostar_pozo(0.75), (
                f"equidad {equidad:.0%} contra {rivales} rival(es): resubo por valor"
            )
        return t.pagar(), f"{detalle_pago}: pago"
    return t.pasar_o_retirarse(), f"{detalle_pago}: me retiro"


def valor_esperado_pagar(equidad, pozo, costo):
    """EV incremental de pagar una apuesta, antes de futuras calles."""
    return equidad * (pozo + costo) - costo


def perfiles_accion_rivales(t, memoria=None):
    """Devuelve la ultima accion publica observada por cada rival activo."""
    cartas_por_etapa = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
    acciones_validas = ("check", "call", "bet", "raise", "allin")
    acciones_recientes = {}
    for registro in t.estado.get("historial_acciones", []):
        id_jugador = registro.get("id_jugador")
        accion = registro.get("accion") or {}
        etapa = registro.get("etapa")
        if (id_jugador == t.mi_id or accion.get("tipo") not in acciones_validas
                or etapa not in cartas_por_etapa):
            continue
        cantidad = cartas_por_etapa[etapa]
        if cantidad > len(t.comunitarias):
            continue
        acciones_recientes[id_jugador] = {
            "tipo": accion["tipo"],
            "etapa": etapa,
            "comunitarias": t.comunitarias[:cantidad],
        }

    perfiles = []
    for jugador in t.estado.get("jugadores", []):
        id_jugador = jugador.get("id")
        if (id_jugador == t.mi_id or not jugador.get("activo")
                or not jugador.get("en_mano", True)):
            continue
        perfil = acciones_recientes.get(id_jugador)
        if perfil is not None and memoria is not None:
            perfil["tendencias"] = memoria.perfil(id_jugador)
        perfiles.append(perfil)
    return perfiles


def _puede_hacer_cbet_seca(t):
    if (t.etapa != "flop" or t.rivales_en_mano != 1 or not t.hablo_ultimo
            or t.subidas_en_esta_calle != 0 or not t.puede("bet")
            or not _flop_seco(t.comunitarias)):
        return False

    agresor = _ultimo_agresor_preflop(t)
    if agresor is None or agresor[0] != t.mi_id:
        return False
    return any(
        registro.get("etapa") == "flop"
        and registro.get("id_jugador") != t.mi_id
        and (registro.get("accion") or {}).get("tipo") == "check"
        for registro in t.estado.get("historial_acciones", [])
    )


def _azar_cbet(t):
    return random.Random(t.estado["id_mano"]).random()


def _flop_seco(comunitarias):
    flop = comunitarias[:3]
    if len(flop) != 3 or len({carta["palo"] for carta in flop}) != 3:
        return False

    rangos = {carta["rango"] for carta in flop}
    if 14 in rangos:
        rangos.add(1)
    return not any(
        sum(rango in rangos for rango in range(inicio, inicio + 5)) >= 3
        for inicio in range(1, 11)
    )
