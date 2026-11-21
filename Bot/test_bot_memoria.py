from contextlib import redirect_stderr
from io import StringIO
import unittest

from bot import jugar
from memoria_rivales import MemoriaRivales


class ConexionFalsa:
    id_jugador = "yo"

    def __init__(self, mensajes):
        self.mensajes = iter(mensajes)

    def recibir(self):
        return next(self.mensajes)


class BotMemoriaTests(unittest.TestCase):
    def test_registra_acciones_y_cartas_reveladas_desde_mensajes_de_mesa(self):
        mesa = [
            {"rango": 14, "palo": 2},
            {"rango": 7, "palo": 1},
            {"rango": 2, "palo": 3},
        ]
        mensajes = [
            {"tipo": "mano_inicio", "cartas": []},
            {
                "tipo": "estado",
                "estado": {
                    "id_mano": "mano-1",
                    "comunitarias": mesa,
                    "historial_acciones": [
                        {
                            "id_jugador": "rival",
                            "etapa": "flop",
                            "accion": {"tipo": "bet"},
                        }
                    ],
                },
            },
            {
                "tipo": "mano_fin",
                "resultado": {
                    "id_mano": "mano-1",
                    "mostradas": {
                        "rival": [
                            {"rango": 14, "palo": 0},
                            {"rango": 13, "palo": 0},
                        ]
                    },
                },
            },
            None,
        ]
        memoria = MemoriaRivales()

        self.assertTrue(jugar(ConexionFalsa(mensajes), True, memoria))

        perfil = memoria.perfil("rival")
        self.assertEqual(perfil["acciones_por_etapa"]["flop"], 1)
        self.assertEqual(perfil["agresiones_mostradas"], 1)
        self.assertAlmostEqual(
            perfil["frecuencia_fuerte_en_agresiones_mostradas"], 2 / 3
        )

    def test_muestra_allins_stacks_y_eliminaciones_en_logs(self):
        mensajes = [
            {"tipo": "mano_inicio", "cartas": []},
            {
                "tipo": "estado",
                "estado": {
                    "id_mano": "mano-2",
                    "historial_acciones": [
                        {
                            "id_jugador": "rival",
                            "etapa": "preflop",
                            "accion": {"tipo": "allin"},
                        }
                    ],
                    "jugadores": [
                        {
                            "id": "yo",
                            "nombre": "Michi Novato",
                            "saldo": 9000,
                            "apuesta_ronda": 100,
                            "en_torneo": True,
                            "allin": False,
                        },
                        {
                            "id": "rival",
                            "nombre": "Rival",
                            "saldo": 0,
                            "apuesta_ronda": 1000,
                            "en_torneo": True,
                            "allin": True,
                        },
                        {
                            "id": "rival-eliminado",
                            "nombre": "Otro rival",
                            "saldo": 0,
                            "apuesta_ronda": 0,
                            "en_torneo": False,
                            "allin": False,
                        },
                    ],
                },
            },
            None,
        ]
        salida = StringIO()

        with redirect_stderr(salida):
            self.assertTrue(jugar(ConexionFalsa(mensajes), False))

        texto = salida.getvalue()
        self.assertIn("[preflop] Rival: allin", texto)
        self.assertIn("Rival: saldo 0, apuesta 1.000 [ALL-IN]", texto)
        self.assertIn("Otro rival agotó sus fichas. Eliminaciones observadas: 1", texto)


if __name__ == "__main__":
    unittest.main()
