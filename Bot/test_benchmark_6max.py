import csv
import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from benchmark_6max import (
    RIVALS,
    SCENARIOS,
    SEATS,
    build_config,
    participants_for_rotation,
    write_stack_history,
)


class Benchmark6MaxTests(unittest.TestCase):
    def test_config_uses_six_player_elimination_rules(self):
        with TemporaryDirectory() as output:
            config = build_config(50, 123, 0, Path(output))

        self.assertEqual(config["formato"], "mesa-unica")
        self.assertFalse(config["reponer_stack"])
        self.assertEqual(config["mesa"]["stack"], 10000)
        self.assertEqual(config["mesa"]["ciega_grande"], 100)
        self.assertEqual(len(config["participantes"]), 6)

    def test_six_rotations_put_each_bot_in_each_seat(self):
        seats_by_bot = {name: set() for _, name in RIVALS}
        seat_ids = None

        for rotation in range(6):
            participants = participants_for_rotation(rotation, 123)
            current_ids = [participant["id"] for participant in participants]
            if seat_ids is None:
                seat_ids = current_ids
            self.assertEqual(current_ids, seat_ids)
            for seat_index, participant in enumerate(participants):
                seats_by_bot[participant["nombre"]].add(seat_index)

        self.assertTrue(all(seats == set(range(6)) for seats in seats_by_bot.values()))

    def test_random_scenarios_have_expected_lineups_and_distinct_seeds(self):
        random_only = participants_for_rotation(0, 123, "random")
        against_darwin = participants_for_rotation(0, 123, "darwin-random")

        self.assertEqual(len(random_only), 6)
        self.assertEqual(sum("aleatorio" in p["nombre"].lower() for p in random_only), 5)
        self.assertEqual(len(against_darwin), 6)
        self.assertEqual(sum("aleatorio" in p["nombre"].lower() for p in against_darwin), 4)
        self.assertIn("Gato Darwin", [p["nombre"] for p in against_darwin])

        seeds = [
            participant["comando"][2]
            for participant in random_only
            if "aleatorio" in participant["nombre"].lower()
        ]
        self.assertEqual(len(set(seeds)), 5)

    def test_rotations_cover_every_seat_in_each_random_scenario(self):
        for scenario in ("random", "darwin-random"):
            seats_by_bot = {
                name: set()
                for _, name in SCENARIOS[scenario]
            }
            for rotation in range(6):
                participants = participants_for_rotation(rotation, 123, scenario)
                for seat_index, participant in enumerate(participants):
                    seats_by_bot[participant["nombre"]].add(seat_index)

            self.assertTrue(
                all(seats == set(range(6)) for seats in seats_by_bot.values()),
                scenario,
            )

    def test_stack_history_csv_records_per_hand_saldo_and_change(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            history = output / "seed-123" / "rotacion-0" / "manos" / "final.jsonl"
            history.parent.mkdir(parents=True)
            hands = [
                {
                    "id_mano": "final-mano-1",
                    "acciones": [
                        {
                            "id_jugador": "asiento-1",
                            "etapa": "preflop",
                            "accion": {"tipo": "allin"},
                        }
                    ],
                    "jugadores": [
                        {
                            "id": "asiento-0",
                            "nombre": "Michi Novato",
                            "saldo": 9900,
                            "apuesta_ronda": 50,
                            "en_torneo": True,
                        },
                        {
                            "id": "asiento-1",
                            "nombre": "Rival",
                            "saldo": 10100,
                            "apuesta_ronda": 100,
                            "en_torneo": True,
                        },
                    ],
                },
                {
                    "id_mano": "final-mano-2",
                    "jugadores": [
                        {"id": "asiento-0", "nombre": "Michi Novato", "saldo": 10050},
                        {
                            "id": "asiento-1",
                            "nombre": "Rival",
                            "saldo": 0,
                            "en_torneo": False,
                        },
                    ],
                },
            ]
            history.write_text(
                "\n".join(json.dumps(hand) for hand in hands) + "\n",
                encoding="utf-8",
            )
            terminal = StringIO()

            with redirect_stdout(terminal):
                report = write_stack_history(output, show_stacks=True)

            with report.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))

        michi = [row for row in rows if row["jugador"] == "Michi Novato"]
        self.assertEqual([(row["fichas"], row["cambio"]) for row in michi],
                         [("9900", "-100"), ("10050", "150")])
        self.assertIn("Michi Novato 9.900 (-100)", terminal.getvalue())
        self.assertIn("Michi Novato 10.050 (+150)", terminal.getvalue())
        rival = [row for row in rows if row["jugador"] == "Rival"]
        self.assertEqual(rival[0]["allin_en_mano"], "True")
        self.assertEqual(rival[0]["allins_acumulados"], "1")
        self.assertEqual(rival[1]["agotó_fichas_en_mano"], "True")
        self.assertEqual(rival[1]["eliminaciones_acumuladas"], "1")
        self.assertIn("All-in: Rival (total 1)", terminal.getvalue())
        self.assertIn("Sin fichas: Rival", terminal.getvalue())


if __name__ == "__main__":
    unittest.main()
