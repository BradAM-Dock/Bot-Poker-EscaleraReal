import unittest

from equidad import estimar_equidad, puntaje_mano


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


if __name__ == "__main__":
    unittest.main()
