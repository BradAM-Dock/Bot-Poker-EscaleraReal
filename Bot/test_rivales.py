import unittest

from memoria_rivales import MemoriaRivales


class MemoriaRivalesTests(unittest.TestCase):
    def test_estima_frecuencias_y_no_cuenta_dos_veces_el_mismo_estado(self):
        estado = {
            "id_mano": "mano-1",
            "comunitarias": [
                {"rango": 14, "palo": 2},
                {"rango": 7, "palo": 1},
                {"rango": 2, "palo": 3},
            ],
            "historial_acciones": [
                {"id_jugador": "rival", "etapa": "preflop", "accion": {"tipo": "call"}},
                {"id_jugador": "otro", "etapa": "preflop", "accion": {"tipo": "raise"}},
                {"id_jugador": "otro", "etapa": "flop", "accion": {"tipo": "bet"}},
                {"id_jugador": "rival", "etapa": "flop", "accion": {"tipo": "fold"}},
            ],
        }
        memoria = MemoriaRivales()

        memoria.observar_estado(estado, "yo")
        memoria.observar_estado(estado, "yo")
        perfil = memoria.perfil("rival")

        self.assertEqual(perfil["decisiones_preflop"], 1)
        self.assertAlmostEqual(perfil["frecuencia_entrada_preflop"], 2 / 3)
        self.assertEqual(perfil["respuestas_a_agresion"]["flop"], 1)
        self.assertAlmostEqual(perfil["frecuencia_fold_ante_agresion"]["flop"], 2 / 3)

    def test_asocia_showdown_con_calle_y_accion_agresiva(self):
        estado = {
            "id_mano": "mano-1",
            "comunitarias": [
                {"rango": 14, "palo": 2},
                {"rango": 7, "palo": 1},
                {"rango": 2, "palo": 3},
            ],
            "historial_acciones": [
                {
                    "id_jugador": "rival",
                    "etapa": "flop",
                    "accion": {"tipo": "bet"},
                }
            ],
        }
        memoria = MemoriaRivales()
        memoria.observar_estado(estado, "yo")
        memoria.observar_resultado(
            {
                "id_mano": "mano-1",
                "mostradas": {
                    "rival": [
                        {"rango": 14, "palo": 0},
                        {"rango": 13, "palo": 0},
                    ]
                },
            },
            "yo",
        )

        perfil = memoria.perfil("rival")
        muestra = perfil["showdowns_por_accion"]["flop"]["bet"]
        self.assertEqual(muestra["muestras"], 1)
        self.assertAlmostEqual(muestra["frecuencia_fuerte"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
