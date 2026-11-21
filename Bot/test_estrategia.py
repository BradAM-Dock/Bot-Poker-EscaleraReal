import unittest
from unittest.mock import patch

from estrategia import _azar_cbet, decidir, perfiles_accion_rivales, postflop


class TurnoFalso:
    def __init__(self, saldo=100, rival_allin=False):
        self.mano = [{}, {}]
        self.comunitarias = [{}, {}, {}]
        self.rivales_en_mano = 1
        self.timeout_ms = 5000
        self.por_igualar = 50
        self.yo = {"saldo": saldo}
        self.mi_id = "yo"
        self.pozo = 100
        self.estado = {
            "historial_acciones": [],
            "jugadores": [
                {"id": "yo", "activo": True, "en_mano": True},
                {
                    "id": "rival",
                    "activo": True,
                    "en_mano": True,
                    "allin": rival_allin,
                },
            ]
        }

    @property
    def porcentaje_para_pagar(self):
        return self.por_igualar * 100 / (self.pozo + self.por_igualar)

    def puede(self, tipo):
        return False

    def pagar(self):
        return {"tipo": "call"}

    def pasar_o_retirarse(self):
        return {"tipo": "fold"}


class TurnoPreflopFalso:
    def __init__(self, pozo=40000, rivales=1):
        self.mano = [{"rango": 14, "palo": 0}, {"rango": 11, "palo": 1}]
        self.comunitarias = []
        self.ciega_grande = 100
        self.apuesta_actual = 10000
        self.por_igualar = 10000
        self.techo = 10000
        self.subida_minima = 200
        self.pozo = pozo
        self.rivales_en_mano = rivales
        self.yo = {"saldo": 10000, "apuesta_ronda": 0}
        self.mi_id = "yo"
        self.ciega_grande = 100
        self.validas = {"call", "allin"}
        self.estado = {
            "id_mano": "mesa-mano-1",
            "historial_acciones": [
                {
                    "id_jugador": "rival",
                    "etapa": "preflop",
                    "accion": {"tipo": "allin"},
                }
            ],
            "jugadores": [
                {"id": "yo", "saldo": 10000, "apuesta_ronda": 0},
                {
                    "id": "rival",
                    "saldo": 10000,
                    "apuesta_ronda": 0,
                    "activo": True,
                    "en_mano": True,
                    "allin": True,
                },
            ],
        }

    def puede(self, tipo):
        return tipo in self.validas

    def apostar(self, monto):
        return {"tipo": "raise", "monto": monto}

    def todo(self):
        return {"tipo": "allin"}

    def pagar(self):
        return {"tipo": "call"}

    def pasar_o_retirarse(self):
        return {"tipo": "fold"}


class TurnoCbetFalso:
    def __init__(self):
        self.mano = [{"rango": 14, "palo": 0}, {"rango": 11, "palo": 1}]
        self.comunitarias = [
            {"rango": 2, "palo": 0},
            {"rango": 7, "palo": 1},
            {"rango": 13, "palo": 2},
        ]
        self.rivales_en_mano = 1
        self.timeout_ms = 5000
        self.por_igualar = 0
        self.yo = {"saldo": 9000, "apuesta_ronda": 0}
        self.mi_id = "yo"
        self.pozo = 1000
        self.etapa = "flop"
        self.hablo_ultimo = True
        self.subidas_en_esta_calle = 0
        self.apuesta_actual = 0
        self.estado = {
            "id_mano": "mesa-mano-1",
            "historial_acciones": [
                {
                    "id_jugador": "yo",
                    "etapa": "preflop",
                    "accion": {"tipo": "raise"},
                },
                {
                    "id_jugador": "rival",
                    "etapa": "preflop",
                    "accion": {"tipo": "call"},
                },
                {
                    "id_jugador": "rival",
                    "etapa": "flop",
                    "accion": {"tipo": "check"},
                },
            ],
            "jugadores": [
                {"id": "yo", "activo": True, "en_mano": True},
                {"id": "rival", "activo": True, "en_mano": True},
            ],
        }
        self.fracciones_apostadas = []

    def puede(self, tipo):
        return tipo == "bet"

    def apostar_pozo(self, fraccion):
        self.fracciones_apostadas.append(fraccion)
        return {"tipo": "bet", "monto": int(self.pozo * fraccion)}

    def pasar_o_retirarse(self):
        return {"tipo": "check"}


class MemoriaPreflopFalsa:
    def __init__(self, tendencias):
        self.tendencias = tendencias
        self.ids_consultados = []

    def perfil(self, id_jugador):
        self.ids_consultados.append(id_jugador)
        return self.tendencias


class PreflopAdaptativoTests(unittest.TestCase):
    def perfil_agresivo(self, acciones=20, agresion=0.6, mostradas=4, fuertes=0.25):
        return {
            "acciones_por_etapa": {"preflop": acciones},
            "frecuencia_agresion": {"preflop": agresion},
            "agresiones_mostradas": mostradas,
            "frecuencia_fuerte_en_agresiones_mostradas": fuertes,
            "showdowns_por_accion": {
                "preflop": {
                    "allin": {
                        "muestras": mostradas,
                        "frecuencia_fuerte": fuertes,
                    }
                }
            },
        }

    def test_paga_con_mano_fuerte_ante_agresor_frecuente_y_buen_precio(self):
        turno = TurnoPreflopFalso(pozo=40000)
        memoria = MemoriaPreflopFalsa(self.perfil_agresivo())

        accion, motivo = decidir(turno, memoria)

        self.assertEqual(accion, {"tipo": "call"})
        self.assertIn("agresor frecuente", motivo)
        self.assertEqual(memoria.ids_consultados, ["rival"])

    def test_no_amplia_el_call_sin_muestra_suficiente(self):
        turno = TurnoPreflopFalso(pozo=40000)
        memoria = MemoriaPreflopFalsa(self.perfil_agresivo(acciones=11))

        accion, _ = decidir(turno, memoria)

        self.assertEqual(accion, {"tipo": "fold"})

    def test_no_amplia_el_call_si_el_agresor_muestra_manos_fuertes(self):
        turno = TurnoPreflopFalso(pozo=40000)
        memoria = MemoriaPreflopFalsa(
            self.perfil_agresivo(mostradas=4, fuertes=0.8)
        )

        accion, _ = decidir(turno, memoria)

        self.assertEqual(accion, {"tipo": "fold"})

    def test_conserva_fold_si_el_precio_es_caro_o_hay_varios_rivales(self):
        memoria = MemoriaPreflopFalsa(self.perfil_agresivo())

        turnos = (
            TurnoPreflopFalso(pozo=10000),
            TurnoPreflopFalso(pozo=40000, rivales=3),
        )
        for turno in turnos:
            with self.subTest(pozo=turno.pozo, rivales=turno.rivales_en_mano):
                accion, _ = decidir(turno, memoria)
                self.assertEqual(accion, {"tipo": "fold"})

    def test_preflop_showdowns_no_se_contaminan_con_manos_postflop(self):
        turno = TurnoPreflopFalso(pozo=40000)
        memoria = MemoriaPreflopFalsa({
            **self.perfil_agresivo(),
            "agresiones_mostradas": 20,
            "frecuencia_fuerte_en_agresiones_mostradas": 0.9,
            "showdowns_por_accion": {
                "river": {
                    "allin": {"muestras": 20, "frecuencia_fuerte": 0.9},
                }
            },
        })

        accion, _ = decidir(turno, memoria)

        self.assertEqual(accion, {"tipo": "call"})


class PreflopAllinTests(unittest.TestCase):
    def preparar_turno(self, mano, stack=10000, rival_stack=10000, apuesta=4000):
        turno = TurnoPreflopFalso()
        turno.mano = mano
        turno.apuesta_actual = apuesta
        turno.por_igualar = 1000
        turno.techo = stack
        turno.yo = {"saldo": stack, "apuesta_ronda": 0}
        turno.estado["historial_acciones"] = [
            {"id_jugador": "rival", "etapa": "preflop",
             "accion": {"tipo": "raise"}},
            {"id_jugador": "rival", "etapa": "preflop",
             "accion": {"tipo": "raise"}},
        ]
        turno.estado["jugadores"] = [
            {"id": "yo", "saldo": stack, "apuesta_ronda": 0},
            {"id": "rival", "saldo": rival_stack, "apuesta_ronda": apuesta,
             "activo": True, "en_mano": True, "allin": False},
        ]
        return turno

    def test_premium_para_allin_con_stack_efectivo_de_hasta_100bb(self):
        casos = (
            ([{"rango": 12, "palo": 0}, {"rango": 12, "palo": 1}],),
            ([{"rango": 14, "palo": 0}, {"rango": 13, "palo": 0}],),
        )
        for (mano,) in casos:
            with self.subTest(mano=mano):
                accion, _ = decidir(self.preparar_turno(mano))
                self.assertEqual(accion, {"tipo": "allin"})

    def test_jj_y_aqo_pagan_una_3bet_sin_ir_allin(self):
        manos = (
            [{"rango": 11, "palo": 0}, {"rango": 11, "palo": 1}],
            [{"rango": 14, "palo": 0}, {"rango": 12, "palo": 1}],
        )
        for mano in manos:
            with self.subTest(mano=mano):
                accion, motivo = decidir(self.preparar_turno(mano))
                self.assertEqual(accion, {"tipo": "call"})
                self.assertIn("pago la 3-bet", motivo)

    def test_ako_no_se_convierte_en_allin(self):
        mano = [{"rango": 14, "palo": 0}, {"rango": 13, "palo": 1}]
        accion, _ = decidir(self.preparar_turno(mano))
        self.assertEqual(accion, {"tipo": "fold"})

    def test_con_stack_profundo_solo_kk_o_mejor_va_allin(self):
        kk = [{"rango": 13, "palo": 0}, {"rango": 13, "palo": 1}]
        qq = [{"rango": 12, "palo": 0}, {"rango": 12, "palo": 1}]

        accion_kk, _ = decidir(self.preparar_turno(kk, stack=15000, apuesta=6000))
        accion_qq, _ = decidir(self.preparar_turno(qq, stack=15000, apuesta=6000))

        self.assertEqual(accion_kk, {"tipo": "allin"})
        self.assertEqual(accion_qq, {"tipo": "call"})

    def test_no_convierte_una_apertura_corta_en_allin_con_mano_no_premium(self):
        turno = self.preparar_turno(
            [{"rango": 9, "palo": 0}, {"rango": 9, "palo": 1}],
            stack=200,
            rival_stack=10000,
            apuesta=100,
        )
        turno.apuesta_actual = 100
        turno.por_igualar = 100
        turno.subida_minima = 200
        turno.validas = {"allin"}
        turno.hablo_ultimo = True

        accion, _ = decidir(turno)

        self.assertEqual(accion, {"tipo": "fold"})


class PostflopEVTests(unittest.TestCase):
    def test_sorteo_de_cbet_es_reproducible_por_id_de_mano(self):
        turno = TurnoCbetFalso()

        self.assertEqual(_azar_cbet(turno), _azar_cbet(turno))

    @patch("estrategia.estimar_equidad", return_value=0.4)
    def test_paga_cuando_ev_supera_el_margen(self, _estimar):
        accion, motivo = postflop(TurnoFalso())
        self.assertEqual(accion, {"tipo": "call"})
        self.assertIn("EV 10.0 fichas", motivo)

    @patch("estrategia.estimar_equidad", return_value=0.35)
    def test_se_retira_cuando_ev_no_cubre_el_margen(self, _estimar):
        accion, motivo = postflop(TurnoFalso())
        self.assertEqual(accion, {"tipo": "fold"})
        self.assertIn("EV 2.5 fichas", motivo)

    @patch("estrategia.estimar_equidad", return_value=0.4)
    def test_conserva_criterio_anterior_si_hay_allin_rival(self, _estimar):
        accion, motivo = postflop(TurnoFalso(rival_allin=True))
        self.assertEqual(accion, {"tipo": "call"})
        self.assertIn("pozo lateral/all-in", motivo)

    @patch("estrategia.estimar_equidad", return_value=0.4)
    def test_call_allin_corto_heads_up_excluye_el_exceso_no_cobrable(self, _estimar):
        accion, motivo = postflop(TurnoFalso(saldo=20))
        self.assertEqual(accion, {"tipo": "call"})
        self.assertIn("EV 16.0 fichas", motivo)

    @patch("estrategia.estimar_equidad", return_value=0.2)
    @patch("estrategia._azar_cbet", return_value=0.64)
    def test_cbet_un_tercio_65_por_ciento_en_flop_seco_heads_up(
        self, _azar, _estimar
    ):
        turno = TurnoCbetFalso()

        accion, motivo = postflop(turno)

        self.assertEqual(accion, {"tipo": "bet", "monto": 333})
        self.assertEqual(turno.fracciones_apostadas, [1 / 3])
        self.assertIn("c-bet 33%", motivo)

    @patch("estrategia.estimar_equidad", return_value=0.9)
    @patch("estrategia._azar_cbet", return_value=0.2)
    def test_cbet_no_depende_de_la_equidad_monte_carlo(self, _azar, _estimar):
        turno = TurnoCbetFalso()

        accion, _ = postflop(turno)

        self.assertEqual(accion["tipo"], "bet")
        self.assertEqual(turno.fracciones_apostadas, [1 / 3])

    @patch("estrategia.estimar_equidad", return_value=0.2)
    @patch("estrategia._azar_cbet", return_value=0.65)
    def test_respeta_la_frecuencia_de_cbet_del_65_por_ciento(self, _azar, _estimar):
        turno = TurnoCbetFalso()

        accion, _ = postflop(turno)

        self.assertEqual(accion, {"tipo": "check"})
        self.assertEqual(turno.fracciones_apostadas, [])

    @patch("estrategia.estimar_equidad", return_value=0.2)
    @patch("estrategia._azar_cbet", return_value=0.2)
    def test_no_hace_cbet_en_flop_de_dos_palos(self, _azar, _estimar):
        turno = TurnoCbetFalso()
        turno.comunitarias[1]["palo"] = 0

        accion, _ = postflop(turno)

        self.assertEqual(accion, {"tipo": "check"})
        self.assertEqual(turno.fracciones_apostadas, [])

    @patch("estrategia.estimar_equidad", return_value=0.2)
    @patch("estrategia._azar_cbet", return_value=0.2)
    def test_no_hace_cbet_en_flop_conectado(self, _azar, _estimar):
        turno = TurnoCbetFalso()
        turno.comunitarias = [
            {"rango": 5, "palo": 0},
            {"rango": 6, "palo": 1},
            {"rango": 7, "palo": 2},
        ]

        accion, _ = postflop(turno)

        self.assertEqual(accion, {"tipo": "check"})
        self.assertEqual(turno.fracciones_apostadas, [])


class PerfilesAccionTests(unittest.TestCase):
    def test_usa_la_accion_mas_reciente_del_rival_activo(self):
        turno = TurnoFalso()
        turno.comunitarias = [
            {"rango": 4, "palo": 3},
            {"rango": 7, "palo": 1},
            {"rango": 2, "palo": 1},
            {"rango": 4, "palo": 2},
        ]
        turno.estado["historial_acciones"] = [
            {"id_jugador": "yo", "etapa": "preflop", "accion": {"tipo": "raise"}},
            {"id_jugador": "rival", "etapa": "flop", "accion": {"tipo": "bet"}},
            {"id_jugador": "rival", "etapa": "turn", "accion": {"tipo": "allin"}},
        ]
        perfiles = perfiles_accion_rivales(turno)

        self.assertEqual(perfiles[0]["tipo"], "allin")
        self.assertEqual(perfiles[0]["comunitarias"], turno.comunitarias)

    def test_la_accion_pasiva_mas_reciente_reemplaza_la_agresion_anterior(self):
        turno = TurnoFalso()
        turno.comunitarias.append({})
        turno.estado["historial_acciones"] = [
            {"id_jugador": "rival", "etapa": "flop", "accion": {"tipo": "bet"}},
            {"id_jugador": "rival", "etapa": "turn", "accion": {"tipo": "call"}},
        ]

        perfiles = perfiles_accion_rivales(turno)

        self.assertEqual(perfiles[0]["tipo"], "call")
        self.assertEqual(perfiles[0]["etapa"], "turn")

    @patch("estrategia.estimar_equidad", return_value=0.2)
    def test_postflop_pasa_el_allin_observado_al_calculo_de_equidad(self, estimar):
        turno = TurnoFalso(rival_allin=True)
        turno.comunitarias = [
            {"rango": 4, "palo": 3},
            {"rango": 7, "palo": 1},
            {"rango": 2, "palo": 1},
            {"rango": 4, "palo": 2},
        ]
        turno.estado["historial_acciones"] = [
            {"id_jugador": "rival", "etapa": "turn", "accion": {"tipo": "allin"}}
        ]

        accion, _ = postflop(turno)

        self.assertEqual(accion, {"tipo": "fold"})
        perfil = estimar.call_args.kwargs["perfiles_rivales"][0]
        self.assertEqual(perfil["tipo"], "allin")
        self.assertEqual(perfil["comunitarias"], turno.comunitarias)

    @patch("estrategia.estimar_equidad", return_value=0.2)
    def test_postflop_pasa_frecuencias_del_rival_al_calculo(self, estimar):
        turno = TurnoFalso(rival_allin=True)
        turno.comunitarias = [
            {"rango": 4, "palo": 3},
            {"rango": 7, "palo": 1},
            {"rango": 2, "palo": 1},
            {"rango": 4, "palo": 2},
        ]
        turno.estado["historial_acciones"] = [
            {"id_jugador": "rival", "etapa": "turn", "accion": {"tipo": "allin"}}
        ]

        class MemoriaFalsa:
            def perfil(self, _id_jugador):
                return {
                    "acciones_por_etapa": {"turn": 10},
                    "frecuencia_agresion": {"turn": 0.8},
                }

        postflop(turno, MemoriaFalsa())

        perfil = estimar.call_args.kwargs["perfiles_rivales"][0]
        self.assertEqual(perfil["tendencias"]["acciones_por_etapa"]["turn"], 10)
        self.assertEqual(perfil["tendencias"]["frecuencia_agresion"]["turn"], 0.8)


if __name__ == "__main__":
    unittest.main()
