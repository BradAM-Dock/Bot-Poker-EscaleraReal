"""Estadisticas bayesianas de las acciones publicas de cada rival."""

from collections import Counter

from cartas import BUENA, MONSTRUO, grupo_preflop, leer_jugada


_ETAPAS = ("preflop", "flop", "turn", "river")
_CARTAS_POR_ETAPA = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}
_ACCIONES_AGRESIVAS = frozenset(("bet", "raise", "allin"))
_ACCIONES_VOLUNTARIAS = frozenset(("call", "bet", "raise", "allin"))
_RESPUESTAS_A_AGRESION = frozenset(("fold", "call", "raise", "allin"))


class _EstadisticasRival:
    def __init__(self):
        self.acciones = Counter()
        self.agresiones = Counter()
        self.respuestas_a_agresion = Counter()
        self.folds_ante_agresion = Counter()
        self.decisiones_preflop = 0
        self.entradas_preflop = 0
        self.agresiones_mostradas = 0
        self.agresiones_fuertes_mostradas = 0
        self.showdowns_por_accion = Counter()
        self.manos_fuertes_por_accion = Counter()

    def perfil(self):
        frecuencia_agresion = {
            etapa: _posterior(self.agresiones[etapa], self.acciones[etapa])
            for etapa in _ETAPAS
        }
        frecuencia_fold = {
            etapa: _posterior(
                self.folds_ante_agresion[etapa],
                self.respuestas_a_agresion[etapa],
            )
            for etapa in _ETAPAS
        }
        showdowns_por_accion = {}
        for clave, muestras in self.showdowns_por_accion.items():
            etapa, tipo = clave
            por_etapa = showdowns_por_accion.setdefault(etapa, {})
            fuertes = self.manos_fuertes_por_accion[clave]
            por_etapa[tipo] = {
                "muestras": muestras,
                "frecuencia_fuerte": _posterior(fuertes, muestras),
            }
        return {
            "acciones_por_etapa": dict(self.acciones),
            "frecuencia_agresion": frecuencia_agresion,
            "respuestas_a_agresion": dict(self.respuestas_a_agresion),
            "frecuencia_fold_ante_agresion": frecuencia_fold,
            "decisiones_preflop": self.decisiones_preflop,
            "frecuencia_entrada_preflop": _posterior(
                self.entradas_preflop, self.decisiones_preflop
            ),
            "agresiones_mostradas": self.agresiones_mostradas,
            "frecuencia_fuerte_en_agresiones_mostradas": _posterior(
                self.agresiones_fuertes_mostradas, self.agresiones_mostradas
            ),
            "showdowns_por_accion": showdowns_por_accion,
        }


def _posterior(exitos, oportunidades):
    return (exitos + 1) / (oportunidades + 2)


class MemoriaRivales:
    """Cuenta tendencias por ID usando solo acciones y cartas reveladas."""

    def __init__(self):
        self._estadisticas = {}
        self.nueva_mano()

    def nueva_mano(self):
        self._id_mano = None
        self._acciones_observadas = 0
        self._agresion_mas_reciente = {}
        self._resultado_observado = None

    def observar_estado(self, estado, mi_id):
        id_mano = estado.get("id_mano")
        if id_mano is not None and id_mano != self._id_mano:
            self.nueva_mano()
            self._id_mano = id_mano

        acciones = estado.get("historial_acciones") or []
        if len(acciones) < self._acciones_observadas:
            return

        for indice in range(self._acciones_observadas, len(acciones)):
            self._observar_accion(acciones, indice, estado, mi_id)
        self._acciones_observadas = len(acciones)

    def _observar_accion(self, acciones, indice, estado, mi_id):
        registro = acciones[indice]
        id_jugador = registro.get("id_jugador")
        etapa = registro.get("etapa")
        accion = registro.get("accion") or {}
        tipo = accion.get("tipo")
        if id_jugador == mi_id or etapa not in _ETAPAS:
            return

        stats = self._estadisticas.setdefault(id_jugador, _EstadisticasRival())
        stats.acciones[etapa] += 1
        if tipo in _ACCIONES_AGRESIVAS:
            stats.agresiones[etapa] += 1
        if etapa == "preflop":
            stats.decisiones_preflop += 1
            if tipo in _ACCIONES_VOLUNTARIAS:
                stats.entradas_preflop += 1

        habia_agresion = any(
            anterior.get("etapa") == etapa
            and (anterior.get("accion") or {}).get("tipo") in _ACCIONES_AGRESIVAS
            for anterior in acciones[:indice]
        )
        if habia_agresion and tipo in _RESPUESTAS_A_AGRESION:
            stats.respuestas_a_agresion[etapa] += 1
            if tipo == "fold":
                stats.folds_ante_agresion[etapa] += 1

        if tipo in _ACCIONES_AGRESIVAS:
            cantidad = _CARTAS_POR_ETAPA[etapa]
            comunitarias = estado.get("comunitarias") or []
            if cantidad <= len(comunitarias):
                self._agresion_mas_reciente[id_jugador] = {
                    "tipo": tipo,
                    "etapa": etapa,
                    "comunitarias": comunitarias[:cantidad],
                }

    def observar_resultado(self, resultado, mi_id):
        id_mano = resultado.get("id_mano")
        if id_mano is not None and id_mano == self._resultado_observado:
            return
        self._resultado_observado = id_mano

        for id_jugador, mano in (resultado.get("mostradas") or {}).items():
            if id_jugador == mi_id or id_jugador not in self._agresion_mas_reciente:
                continue
            if len(mano) != 2:
                continue

            agresion = self._agresion_mas_reciente[id_jugador]
            stats = self._estadisticas[id_jugador]
            stats.agresiones_mostradas += 1
            clave = (agresion["etapa"], agresion["tipo"])
            stats.showdowns_por_accion[clave] += 1
            if _mano_fuerte_en_agresion(mano, agresion):
                stats.agresiones_fuertes_mostradas += 1
                stats.manos_fuertes_por_accion[clave] += 1

    def perfil(self, id_jugador):
        stats = self._estadisticas.get(id_jugador)
        if stats is None:
            return _EstadisticasRival().perfil()
        return stats.perfil()


def _mano_fuerte_en_agresion(mano, agresion):
    comunitarias = agresion["comunitarias"]
    if not comunitarias:
        return grupo_preflop(mano) in ("premium", "fuerte")
    return leer_jugada(mano, comunitarias).nivel in (BUENA, MONSTRUO)
