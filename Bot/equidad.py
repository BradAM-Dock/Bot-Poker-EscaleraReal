"""Estimacion de equidad postflop mediante simulaciones Monte Carlo."""

import random
import time

from cartas import BUENA, MONSTRUO, grupo_preflop, leer_jugada


SIMULACIONES_POR_DEFECTO = 2000
PRESUPUESTO_MS_MAXIMO = 450
_RANGOS = range(2, 15)
_PALOS = range(4)
_PESOS_POSTFLOP = {
    "check": (0.9, 1.05, 1.1, 0.95, 0.95, 0.95, 0.9, 0.9, 0.9),
    "call": (0.25, 1.3, 1.6, 1.3, 1.15, 1.15, 0.85, 0.75, 0.75),
    "bet": (0.35, 0.65, 1.2, 2.0, 2.4, 2.6, 3.2, 3.8, 4.5),
    "raise": (0.2, 0.55, 1.4, 3.0, 3.6, 4.0, 5.0, 6.0, 7.0),
    "allin": (0.12, 0.4, 1.5, 5.5, 6.0, 6.5, 8.0, 9.0, 10.0),
}
_PESOS_PREFLOP = {
    "check": {"premium": 1.0, "fuerte": 1.0, "jugable": 1.0, "especulativa": 1.0, "basura": 1.0},
    "call": {"premium": 0.8, "fuerte": 1.3, "jugable": 1.4, "especulativa": 1.5, "basura": 0.7},
    "bet": {"premium": 4.0, "fuerte": 2.2, "jugable": 1.2, "especulativa": 0.8, "basura": 0.5},
    "raise": {"premium": 5.0, "fuerte": 2.5, "jugable": 1.1, "especulativa": 0.6, "basura": 0.3},
    "allin": {"premium": 9.0, "fuerte": 4.0, "jugable": 1.0, "especulativa": 0.5, "basura": 0.15},
}
_PESO_POR_OUT = {
    "check": 0.04,
    "call": 0.14,
    "bet": 0.08,
    "raise": 0.16,
    "allin": 0.3,
}


def puntaje_mano(cartas):
    """Devuelve una tupla comparable: categoria y desempates de 5 a 7 cartas."""
    rangos = [carta["rango"] for carta in cartas]
    palos = [carta["palo"] for carta in cartas]
    conteo = {rango: rangos.count(rango) for rango in set(rangos)}
    por_cantidad = sorted(conteo, key=lambda rango: (conteo[rango], rango), reverse=True)

    rangos_por_palo = {}
    for carta in cartas:
        rangos_por_palo.setdefault(carta["palo"], set()).add(carta["rango"])

    for rangos_color in rangos_por_palo.values():
        if len(rangos_color) >= 5:
            alta = _alta_escalera(rangos_color)
            if alta:
                return (8, alta)

    cuatros = [r for r in por_cantidad if conteo[r] == 4]
    if cuatros:
        kicker = max(r for r in rangos if r != cuatros[0])
        return (7, cuatros[0], kicker)

    trios = [r for r in por_cantidad if conteo[r] >= 3]
    if trios:
        pares = [r for r in por_cantidad if r != trios[0] and conteo[r] >= 2]
        if pares:
            return (6, trios[0], pares[0])

    colores = [sorted(rs, reverse=True) for rs in rangos_por_palo.values() if len(rs) >= 5]
    if colores:
        return (5, *max(colores)[:5])

    alta = _alta_escalera(set(rangos))
    if alta:
        return (4, alta)

    if trios:
        kickers = sorted((r for r in rangos if r != trios[0]), reverse=True)[:2]
        return (3, trios[0], *kickers)

    pares = [r for r in por_cantidad if conteo[r] >= 2]
    if len(pares) >= 2:
        kicker = max(r for r in rangos if r not in pares[:2])
        return (2, pares[0], pares[1], kicker)
    if pares:
        kickers = sorted((r for r in rangos if r != pares[0]), reverse=True)[:3]
        return (1, pares[0], *kickers)

    return (0, *sorted(rangos, reverse=True)[:5])


def _alta_escalera(rangos):
    """Retorna la carta mas alta de una escalera; el as tambien puede ser 1."""
    valores = set(rangos)
    if 14 in valores:
        valores.add(1)
    for alta in range(14, 4, -1):
        if all(rango in valores for rango in range(alta - 4, alta + 1)):
            return alta
    return 0


def estimar_equidad(mano, comunitarias, rivales, simulaciones=SIMULACIONES_POR_DEFECTO,
                    timeout_ms=None, perfiles_rivales=None, azar=None):
    """Estima la fraccion del pozo que gana, contando empates proporcionalmente."""
    if len(mano) != 2 or not 3 <= len(comunitarias) <= 5:
        raise ValueError("se requieren dos cartas propias y de tres a cinco comunitarias")
    if rivales < 0:
        raise ValueError("la cantidad de rivales no puede ser negativa")
    if simulaciones <= 0:
        raise ValueError("simulaciones debe ser mayor que cero")
    if perfiles_rivales is None:
        perfiles_rivales = [None] * rivales
    elif len(perfiles_rivales) != rivales:
        raise ValueError("debe haber un perfil por cada rival")
    for perfil in perfiles_rivales:
        if perfil is None:
            continue
        if perfil.get("tipo") not in _PESOS_POSTFLOP:
            raise ValueError("tipo de accion invalido en perfil rival")
        cartas_vistas = perfil.get("comunitarias") or []
        if len(cartas_vistas) not in (0, 3, 4, 5):
            raise ValueError("el perfil rival debe tener 0, 3, 4 o 5 cartas comunitarias")

    conocidas = mano + comunitarias
    ids_conocidos = [_id_carta(carta) for carta in conocidas]
    if len(set(ids_conocidos)) != len(ids_conocidos):
        raise ValueError("hay cartas repetidas entre la mano y la mesa")
    if rivales == 0:
        return 1.0

    ids_set = set(ids_conocidos)
    mazo = [
        {"rango": rango, "palo": palo}
        for rango in _RANGOS
        for palo in _PALOS
        if (rango, palo) not in ids_set
    ]
    faltan_mesa = 5 - len(comunitarias)
    necesarias = faltan_mesa + 2 * rivales
    if necesarias > len(mazo):
        raise ValueError("hay mas cartas necesarias que cartas disponibles")

    if timeout_ms is None or timeout_ms <= 0:
        presupuesto_ms = PRESUPUESTO_MS_MAXIMO
    else:
        presupuesto_ms = max(1, min(PRESUPUESTO_MS_MAXIMO, int(timeout_ms * 0.6)))
    limite = time.monotonic() + presupuesto_ms / 1000
    azar = azar or random.Random()
    acumulado = 0.0
    peso_total = 0.0
    realizadas = 0

    while realizadas < simulaciones:
        if realizadas % 16 == 0 and realizadas and time.monotonic() >= limite:
            break

        repartidas = azar.sample(mazo, necesarias)
        mesa = comunitarias + repartidas[:faltan_mesa]
        puntaje_propio = puntaje_mano(mano + mesa)
        mejores = [puntaje_propio]
        inicio = faltan_mesa
        peso_muestra = 1.0
        for indice in range(rivales):
            mano_rival = repartidas[inicio + 2 * indice:inicio + 2 * indice + 2]
            mejores.append(puntaje_mano(mano_rival + mesa))
            perfil = perfiles_rivales[indice]
            if perfil is not None:
                peso_muestra *= _peso_accion_rival(mano_rival, perfil)

        mejor_puntaje = max(mejores)
        if puntaje_propio == mejor_puntaje:
            acumulado += peso_muestra / mejores.count(mejor_puntaje)
        peso_total += peso_muestra
        realizadas += 1

    return acumulado / peso_total


def _peso_accion_rival(mano, perfil):
    """Likelihood heuristico de la accion dado el valor y los proyectos de la mano."""
    tipo = perfil["tipo"]
    comunitarias = perfil.get("comunitarias") or []
    if not comunitarias:
        grupo = grupo_preflop(mano)
        peso = _PESOS_PREFLOP[tipo][grupo]
        mano_fuerte = grupo in ("premium", "fuerte")
    else:
        lectura = leer_jugada(mano, comunitarias)
        nivel = puntaje_mano(mano + comunitarias)[0]
        peso = _PESOS_POSTFLOP[tipo][nivel] * (
            1 + _PESO_POR_OUT[tipo] * lectura.outs
        )
        mano_fuerte = lectura.nivel in (BUENA, MONSTRUO)
    return _ajustar_peso_por_tendencias(peso, mano_fuerte, perfil)


def _ajustar_peso_por_tendencias(peso, mano_fuerte, perfil):
    tendencias = perfil.get("tendencias")
    if not tendencias:
        return peso

    tipo = perfil.get("tipo")
    etapa = perfil.get("etapa")
    acciones = tendencias.get("acciones_por_etapa", {}).get(etapa, 0)
    frecuencia = tendencias.get("frecuencia_agresion", {}).get(etapa, 0.5)
    confianza = acciones / (acciones + 8) if acciones else 0
    if tipo in ("bet", "raise", "allin"):
        sensibilidad = 1 + 1.5 * (0.5 - frecuencia) * confianza
        peso = 1 + (peso - 1) * sensibilidad
    elif tipo == "call":
        if etapa == "preflop":
            decisiones = tendencias.get("decisiones_preflop", 0)
            entrada = tendencias.get("frecuencia_entrada_preflop", 0.5)
            confianza_entrada = decisiones / (decisiones + 8) if decisiones else 0
            amplitud = (entrada - 0.5) * 2 * confianza_entrada
            peso *= 1 - 0.5 * amplitud if mano_fuerte else 1 + 0.5 * amplitud
        else:
            respuestas = tendencias.get("respuestas_a_agresion", {}).get(etapa, 0)
            folds = tendencias.get("frecuencia_fold_ante_agresion", {}).get(etapa, 0.5)
            confianza_fold = respuestas / (respuestas + 8) if respuestas else 0
            evidencia_fold = (folds - 0.5) * 2 * confianza_fold
            peso *= 1 + 0.5 * evidencia_fold if mano_fuerte else 1 - 0.5 * evidencia_fold

    muestra_accion = (
        tendencias.get("showdowns_por_accion", {})
        .get(etapa, {})
        .get(tipo)
    )
    if muestra_accion and muestra_accion.get("muestras", 0):
        showdowns = muestra_accion["muestras"]
        frecuencia_fuerte = muestra_accion.get("frecuencia_fuerte", 0.5)
    else:
        showdowns = tendencias.get("agresiones_mostradas", 0)
        frecuencia_fuerte = tendencias.get(
            "frecuencia_fuerte_en_agresiones_mostradas", 0.5
        )
    if showdowns:
        confianza_showdown = showdowns / (showdowns + 8)
        evidencia = (frecuencia_fuerte - 0.5) * 2 * confianza_showdown
        peso *= 1 + evidencia if mano_fuerte else 1 - evidencia * 0.5
    return max(0.05, peso)


def _id_carta(carta):
    rango = carta.get("rango")
    palo = carta.get("palo")
    if rango not in _RANGOS or palo not in _PALOS:
        raise ValueError(f"carta invalida: {carta!r}")
    return rango, palo
