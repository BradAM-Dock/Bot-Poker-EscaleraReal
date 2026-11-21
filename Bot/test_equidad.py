import random
import unittest

from equidad import _peso_accion_rival, estimar_equidad, puntaje_mano
from estrategia import valor_esperado_pagar


def carta(rango, palo):
    return {"rango": rango, "palo": palo}


class PuntajeManoTests(unittest.TestCase):
    def test_compara_kickers_de_parejas(self):
        pareja_con_rey = [
            carta(14, 0), carta(14, 1), carta(13, 0),
            carta(9, 1), carta(7, 2), carta(5, 3), carta(2, 0),
        ]
        pareja_con_ocho = [
            carta(14, 2), carta(14, 3), carta(8, 0),
            carta(9, 1), carta(7, 2), carta(5, 3), carta(2, 0),
        ]
        self.assertGreater(puntaje_mano(pareja_con_rey), puntaje_mano(pareja_con_ocho))

    def test_detecta_escalera_baja_con_as(self):
        mano = [carta(14, 0), carta(2, 1), carta(3, 2), carta(4, 3), carta(5, 0)]
        self.assertEqual(puntaje_mano(mano), (4, 5))

    def test_detecta_escalera_de_color(self):
        mano = [
            carta(10, 3), carta(11, 3), carta(12, 3), carta(13, 3),
            carta(14, 3), carta(2, 0), carta(3, 1),
        ]
        self.assertEqual(puntaje_mano(mano), (8, 14))

    def test_dos_trios_forman_full_house(self):
        mano = [
            carta(14, 0), carta(14, 1), carta(14, 2),
            carta(13, 0), carta(13, 1), carta(13, 2), carta(2, 0),
        ]
        self.assertEqual(puntaje_mano(mano), (6, 14, 13))


class EquidadTests(unittest.TestCase):
    def test_tablero_de_escalera_real_empata_a_todos(self):
        mano = [carta(2, 0), carta(3, 1)]
        mesa = [carta(10, 3), carta(11, 3), carta(12, 3), carta(13, 3), carta(14, 3)]
        self.assertAlmostEqual(estimar_equidad(mano, mesa, 2, simulaciones=20), 1 / 3)

    def test_rechaza_cartas_repetidas(self):
        mano = [carta(14, 0), carta(14, 0)]
        mesa = [carta(2, 1), carta(3, 2), carta(4, 3)]
        with self.assertRaises(ValueError):
            estimar_equidad(mano, mesa, 1, simulaciones=1)

    def test_allin_en_turno_pondera_trios_sobre_manos_debiles(self):
        mano = [carta(3, 0), carta(3, 2)]
        mesa = [carta(4, 3), carta(7, 1), carta(2, 1), carta(4, 2)]
        perfil = {"tipo": "allin", "comunitarias": mesa}

        aleatoria = estimar_equidad(
            mano, mesa, 1, perfiles_rivales=[None], azar=random.Random(42)
        )
        filtrada = estimar_equidad(
            mano, mesa, 1, perfiles_rivales=[perfil], azar=random.Random(42)
        )

        self.assertLess(filtrada, aleatoria - 0.15)
        self.assertLess(filtrada, 0.48)

    def test_tendencias_del_rival_vuelven_menos_informativo_su_allin_frecuente(self):
        mesa = [carta(4, 3), carta(7, 1), carta(2, 1), carta(4, 2)]
        fuerte = [carta(4, 0), carta(9, 3)]
        debil = [carta(8, 0), carta(10, 2)]
        perfil = {"tipo": "allin", "etapa": "turn", "comunitarias": mesa}
        peso_fuerte_base = _peso_accion_rival(fuerte, perfil)
        peso_debil_base = _peso_accion_rival(debil, perfil)
        perfil["tendencias"] = {
            "acciones_por_etapa": {"turn": 30},
            "frecuencia_agresion": {"turn": 0.9},
        }

        peso_fuerte_ajustado = _peso_accion_rival(fuerte, perfil)
        peso_debil_ajustado = _peso_accion_rival(debil, perfil)

        self.assertLess(peso_fuerte_ajustado, peso_fuerte_base)
        self.assertGreater(peso_debil_ajustado, peso_debil_base)

    def test_historial_de_fold_hace_mas_fuerte_el_rango_de_call(self):
        mesa = [carta(4, 3), carta(7, 1), carta(2, 1), carta(4, 2)]
        fuerte = [carta(4, 0), carta(9, 3)]
        debil = [carta(8, 0), carta(10, 2)]
        perfil = {"tipo": "call", "etapa": "turn", "comunitarias": mesa}
        peso_fuerte_base = _peso_accion_rival(fuerte, perfil)
        peso_debil_base = _peso_accion_rival(debil, perfil)
        perfil["tendencias"] = {
            "respuestas_a_agresion": {"turn": 30},
            "frecuencia_fold_ante_agresion": {"turn": 0.9},
        }

        peso_fuerte_ajustado = _peso_accion_rival(fuerte, perfil)
        peso_debil_ajustado = _peso_accion_rival(debil, perfil)

        self.assertGreater(peso_fuerte_ajustado, peso_fuerte_base)
        self.assertLess(peso_debil_ajustado, peso_debil_base)

    def test_showdowns_del_mismo_tipo_de_accion_calibran_el_rango(self):
        mesa = [carta(4, 3), carta(7, 1), carta(2, 1), carta(4, 2)]
        fuerte = [carta(4, 0), carta(9, 3)]
        debil = [carta(8, 0), carta(10, 2)]

        def perfil(frecuencia_fuerte):
            return {
                "tipo": "allin",
                "etapa": "turn",
                "comunitarias": mesa,
                "tendencias": {
                    "showdowns_por_accion": {
                        "turn": {
                            "allin": {
                                "muestras": 20,
                                "frecuencia_fuerte": frecuencia_fuerte,
                            }
                        }
                    }
                },
            }

        rango_fuerte = perfil(0.9)
        rango_debil = perfil(0.1)
        razon_fuerte = (
            _peso_accion_rival(fuerte, rango_fuerte)
            / _peso_accion_rival(debil, rango_fuerte)
        )
        razon_debil = (
            _peso_accion_rival(fuerte, rango_debil)
            / _peso_accion_rival(debil, rango_debil)
        )

        self.assertGreater(razon_fuerte, razon_debil)


class ValorEsperadoTests(unittest.TestCase):
    def test_ev_positivo_si_la_equidad_supera_el_precio(self):
        self.assertAlmostEqual(valor_esperado_pagar(0.5, 100, 50), 25)

    def test_ev_cero_en_el_punto_de_equilibrio(self):
        self.assertAlmostEqual(valor_esperado_pagar(1 / 3, 100, 50), 0)

    def test_ev_negativo_si_la_equidad_no_cubre_el_costo(self):
        self.assertAlmostEqual(valor_esperado_pagar(0.2, 100, 50), -20)


if __name__ == "__main__":
    unittest.main()
