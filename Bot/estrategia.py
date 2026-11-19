"""Estrategia de Michi Novato: reglas preflop y equidad Monte Carlo postflop.

La estrategia preflop usa reglas y despues del flop estima la equidad contra
manos aleatorias para valorar apuestas y pagos.

decidir() devuelve la accion y un motivo en texto, que se imprime en los logs
para que puedas seguir lo que piensa el bot mano a mano.

Ideas de poker que usa (todas explicadas donde aparecen):
  - Tabla de manos iniciales: con que dos cartas vale la pena entrar.
  - Simulaciones Monte Carlo para estimar la fraccion esperada del pozo.
  - Pot odds y cantidad de rivales al decidir si pagar o apostar.
"""

from cartas import grupo_preflop
from equidad import estimar_equidad


def decidir(turno):
    if len(turno.comunitarias) < 3:
        return preflop(turno)
    return postflop(turno)


# --- Antes del flop -------------------------------------------------------------

def preflop(t):
    grupo = grupo_preflop(t.mano)
    cg = t.ciega_grande
    # Si la apuesta mas alta es la ciega grande, nadie subio todavia.
    nadie_subio = t.apuesta_actual <= cg

    if grupo == "premium":
        if nadie_subio:
            return t.apostar(3 * cg), "premium: abro a 3 ciegas"
        if t.apuesta_actual * 3 >= t.techo:
            return t.todo(), "premium contra subida grande: all-in"
        return t.apostar(3 * t.apuesta_actual), "premium: resubo al triple"

    if grupo == "fuerte":
        if nadie_subio:
            return t.apostar(3 * cg), "fuerte: abro a 3 ciegas"
        if t.por_igualar <= 4 * cg:
            return t.pagar(), "fuerte: pago una subida normal"
        return t.pasar_o_retirarse(), "fuerte, pero la subida es enorme"

    if grupo == "jugable":
        if nadie_subio and t.hablo_ultimo:
            # En el boton, si nadie entro, subir roba las ciegas seguido.
            return t.apostar(3 * cg), "jugable en buena posicion: intento robar las ciegas"
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


# --- Despues del flop -------------------------------------------------------------

def postflop(t):
    equidad = estimar_equidad(
        t.mano,
        t.comunitarias,
        t.rivales_en_mano,
        timeout_ms=t.timeout_ms,
    )
    rivales = t.rivales_en_mano

    if t.por_igualar == 0:
        umbral_apuesta = min(0.82, 0.62 + 0.04 * max(0, rivales - 1))
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
    precio = t.porcentaje_para_pagar / 100
    if equidad >= precio + margen:
        umbral_subida = min(0.91, 0.84 + 0.03 * max(0, rivales - 1))
        if equidad >= umbral_subida and t.puede("raise"):
            return t.apostar_pozo(0.75), (
                f"equidad {equidad:.0%} contra {rivales} rival(es): resubo por valor"
            )
        return t.pagar(), (
            f"equidad {equidad:.0%} supera precio {precio:.0%} "
            f"+ margen {margen:.0%}: pago"
        )
    return t.pasar_o_retirarse(), (
        f"equidad {equidad:.0%} insuficiente para precio {precio:.0%} "
        f"+ margen {margen:.0%}: me retiro"
    )
