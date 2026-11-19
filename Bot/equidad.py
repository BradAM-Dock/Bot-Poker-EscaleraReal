"""Estimacion de equidad postflop mediante simulaciones Monte Carlo."""

import random
import time


SIMULACIONES_POR_DEFECTO = 500
PRESUPUESTO_MS_MAXIMO = 450
_RANGOS = range(2, 15)
_PALOS = range(4)


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
                    timeout_ms=None):
    """Estima la fraccion del pozo que gana, contando empates proporcionalmente."""
    if len(mano) != 2 or not 3 <= len(comunitarias) <= 5:
        raise ValueError("se requieren dos cartas propias y de tres a cinco comunitarias")
    if rivales < 0:
        raise ValueError("la cantidad de rivales no puede ser negativa")
    if simulaciones <= 0:
        raise ValueError("simulaciones debe ser mayor que cero")

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
    azar = random.Random()
    acumulado = 0.0
    realizadas = 0

    while realizadas < simulaciones:
        if realizadas % 16 == 0 and realizadas and time.monotonic() >= limite:
            break

        repartidas = azar.sample(mazo, necesarias)
        mesa = comunitarias + repartidas[:faltan_mesa]
        puntaje_propio = puntaje_mano(mano + mesa)
        mejores = [puntaje_propio]
        inicio = faltan_mesa
        for indice in range(rivales):
            mano_rival = repartidas[inicio + 2 * indice:inicio + 2 * indice + 2]
            mejores.append(puntaje_mano(mano_rival + mesa))

        mejor_puntaje = max(mejores)
        if puntaje_propio == mejor_puntaje:
            acumulado += 1 / mejores.count(mejor_puntaje)
        realizadas += 1

    return acumulado / realizadas


def _id_carta(carta):
    rango = carta.get("rango")
    palo = carta.get("palo")
    if rango not in _RANGOS or palo not in _PALOS:
        raise ValueError(f"carta invalida: {carta!r}")
    return rango, palo
