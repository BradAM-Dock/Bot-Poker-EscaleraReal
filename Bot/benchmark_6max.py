#!/usr/bin/env python3
"""Simula mesas de seis con distintos grupos de rivales y rota los asientos."""

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parent
REPO_DIR = BOT_DIR.parent
KIT_DIR = REPO_DIR / "pokerfight-arena-participantes-main"
BIN_DIR = KIT_DIR / "bin"
ARENA = BIN_DIR / ("arena.exe" if sys.platform == "win32" else "arena")
SEATS = [f"asiento-{index}" for index in range(6)]
STACK_INICIAL = 10000
RIVALS = [
    ("novato", "Michi Novato"),
    ("darwin", "Gato Darwin"),
    ("base", "Bot Base"),
    ("estadistico", "Bot Estadistico"),
    ("bandido", "Gato Bandido"),
    ("espia", "Michi Espia"),
]
SCENARIOS = {
    "kit": RIVALS,
    "random": [
        ("novato", "Michi Novato"),
        *((f"aleatorio-{index}", f"Aleatorio {index}") for index in range(1, 6)),
    ],
    "darwin-random": [
        ("novato", "Michi Novato"),
        ("darwin", "Gato Darwin"),
        *((f"aleatorio-{index}", f"Aleatorio {index}") for index in range(1, 5)),
    ],
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simula mesas de seis bots y rota los asientos."
    )
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS,
        default="kit",
        help="kit (default), random (cinco aleatorios) o darwin-random",
    )
    parser.add_argument("--hands", type=int, default=50, help="limite de manos por mesa")
    parser.add_argument("--seed", type=int, default=20261123, help="primera semilla")
    parser.add_argument("--seeds", type=int, default=3, help="cantidad de semillas")
    parser.add_argument(
        "--rotations",
        type=int,
        default=6,
        help="rotaciones de asiento por semilla (1-6; default: 6)",
    )
    parser.add_argument(
        "--show-stacks",
        action="store_true",
        help="imprime las fichas y su cambio al cierre de cada mano",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="directorio nuevo para guardar resultados e historiales",
    )
    return parser.parse_args()


def command_for(bot_id, seed):
    if bot_id == "novato":
        return [sys.executable, str(BOT_DIR / "bot.py"), "-silencioso"]
    if bot_id == "darwin":
        return [
            str(BIN_DIR / ("darwin.exe" if sys.platform == "win32" else "darwin")),
            "-silencioso",
            "-semilla",
            str(seed),
        ]
    if bot_id.startswith("aleatorio-"):
        indice = int(bot_id.rsplit("-", 1)[1])
        executable = BIN_DIR / ("aleatorio.exe" if sys.platform == "win32" else "aleatorio")
        return [
            str(executable),
            "-semilla",
            str(seed * 16 + indice),
        ]
    if bot_id == "estadistico":
        return [
            str(BIN_DIR / ("estadistico.exe" if sys.platform == "win32" else "estadistico")),
            "-simulaciones",
            "2000",
        ]
    flags = ["-silencioso"] if bot_id in ("bandido", "espia") else []
    executable = BIN_DIR / (f"{bot_id}.exe" if sys.platform == "win32" else bot_id)
    return [str(executable), *flags]


def participants_for_rotation(rotation, seed, scenario="kit"):
    participants = []
    rivals = SCENARIOS[scenario]
    for seat_index, seat_id in enumerate(SEATS):
        bot_id, name = rivals[(seat_index + rotation) % len(rivals)]
        participants.append(
            {
                "id": seat_id,
                "nombre": name,
                "comando": command_for(bot_id, seed),
                "directorio": str(KIT_DIR),
            }
        )
    return participants


def build_config(hands, seed, rotation, output, scenario="kit"):
    return {
        "nombre": f"novato-6max-{scenario}-seed-{seed}-rotacion-{rotation}",
        "formato": "mesa-unica",
        "puntuacion": "puestos",
        "manos_por_enfrentamiento": hands,
        "ida_y_vuelta": False,
        "reponer_stack": False,
        "semilla": seed,
        "paralelismo": 1,
        "penalizacion_timeout": 0,
        "guardar_historial": True,
        "salida": str(output),
        "mesa": {
            "ciega_chica": 50,
            "ciega_grande": 100,
            "stack": STACK_INICIAL,
            "timeout_ms": 5000,
            "espera_jugadores_ms": 15000,
        },
        "participantes": participants_for_rotation(rotation, seed, scenario),
    }


def add_result(totals, puesto):
    nombre = puesto["nombre"]
    total = totals[nombre]
    total["partidas"] += 1
    total["fichas"] += puesto["fichas"]
    total["neto"] += puesto["neto"]
    total["posiciones"] += puesto["posicion"]
    total["ganadas"] += puesto["posicion"] == 1
    total["top3"] += puesto["posicion"] <= 3
    total["eliminaciones"] += puesto["fichas"] == 0
    total["timeouts"] += puesto["timeouts"]


def stack_history_files(output):
    files = sorted(output.glob("**/manos/*.jsonl"))
    if not files:
        raise SystemExit(f"No se encontraron historiales de manos en {output}.")
    return files


def _route_number(path, prefix):
    for part in path.parts:
        if part.startswith(prefix):
            return int(part[len(prefix):])
    raise ValueError(f"No se encontró '{prefix}' en la ruta {path}.")


def _format_chips(amount):
    return f"{amount:,}".replace(",", ".")


def write_stack_history(output, show_stacks=False):
    history_path = output / "fichas_por_mano.csv"
    fields = (
        "semilla", "rotacion", "mano", "id_mano",
        "id_jugador", "jugador", "fichas", "cambio",
        "allin_en_mano", "allins_acumulados",
        "agotó_fichas_en_mano", "eliminaciones_acumuladas",
    )

    if show_stacks:
        print("\nEvolución de fichas al cierre de cada mano:")
    with history_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for source in stack_history_files(output):
            seed = _route_number(source, "seed-")
            rotation = _route_number(source, "rotacion-")
            previous = {}
            allins = {}
            eliminations = {}
            if show_stacks:
                print(f"\nSemilla {seed} | rotación {rotation}:")

            with source.open(encoding="utf-8") as hands:
                for hand_number, line in enumerate(hands, start=1):
                    if not line.strip():
                        continue
                    hand = json.loads(line)
                    players = hand.get("jugadores")
                    if not isinstance(players, list):
                        raise ValueError(
                            f"Historial sin jugadores en {source}, mano {hand_number}."
                        )

                    names = {
                        player["id"]: player["nombre"]
                        for player in players
                    }
                    allin_ids = {
                        action.get("id_jugador")
                        for action in hand.get("acciones", [])
                        if (action.get("accion") or {}).get("tipo") == "allin"
                    }
                    for player_id in allin_ids:
                        allins[player_id] = allins.get(player_id, 0) + 1

                    current = {}
                    display = []
                    eliminated_this_hand = []
                    for player in players:
                        player_id = player["id"]
                        name = player["nombre"]
                        # The arena's saved saldo is the stack after the hand;
                        # apuesta_ronda is contribution metadata, not extra chips.
                        chips = player["saldo"]
                        previous_chips = previous.get(player_id, STACK_INICIAL)
                        change = chips - previous_chips
                        eliminated = (
                            player.get("en_torneo") is False
                            and previous_chips > 0
                            and chips == 0
                        )
                        if eliminated:
                            eliminations[player_id] = eliminations.get(player_id, 0) + 1
                            eliminated_this_hand.append(name)
                        current[player_id] = chips
                        writer.writerow({
                            "semilla": seed,
                            "rotacion": rotation,
                            "mano": hand_number,
                            "id_mano": hand["id_mano"],
                            "id_jugador": player_id,
                            "jugador": name,
                            "fichas": chips,
                            "cambio": change,
                            "allin_en_mano": player_id in allin_ids,
                            "allins_acumulados": allins.get(player_id, 0),
                            "agotó_fichas_en_mano": eliminated,
                            "eliminaciones_acumuladas": eliminations.get(player_id, 0),
                        })
                        estados = []
                        if player_id in allin_ids:
                            estados.append(f"ALL-IN #{allins[player_id]}")
                        if player.get("en_torneo") is False:
                            estados.append(
                                f"ELIMINADO #{eliminations.get(player_id, 0)}"
                            )
                        etiqueta = f" [{', '.join(estados)}]" if estados else ""
                        display.append(
                            f"{name} {_format_chips(chips)} "
                            f"({_format_chips(change) if change < 0 else '+' + _format_chips(change)})"
                            f"{etiqueta}"
                        )

                    if show_stacks:
                        print(
                            f"  Mano {hand_number:02} [{hand['id_mano']}]: "
                            + " | ".join(display)
                        )
                        if allin_ids:
                            allin_names = [
                                f"{names.get(player_id, player_id)} "
                                f"(total {allins[player_id]})"
                                for player_id in sorted(allin_ids, key=str)
                            ]
                            print("    All-in: " + ", ".join(allin_names))
                        if eliminated_this_hand:
                            print("    Sin fichas: " + ", ".join(eliminated_this_hand))
                    previous = current

    return history_path


def print_results(output, rivals, show_stacks=False):
    totals = {
        name: {
            "partidas": 0,
            "fichas": 0,
            "neto": 0,
            "posiciones": 0,
            "ganadas": 0,
            "top3": 0,
            "eliminaciones": 0,
            "timeouts": 0,
        }
        for _, name in rivals
    }
    hubo_error = False

    for result_path in sorted(output.glob("**/enfrentamientos.jsonl")):
        for line in result_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            result = json.loads(line)
            if result.get("error"):
                hubo_error = True
                print(f"ERROR {result['id']}: {result['error']}")
                continue
            for puesto in result["puestos"]:
                add_result(totals, puesto)

    print("\nResumen por bot:")
    print("  Bot                 fichas netas  puesto medio  gana  top 3  eliminaciones  timeouts")
    for _, name in rivals:
        total = totals[name]
        partidas = total["partidas"]
        if not partidas:
            hubo_error = True
            print(f"  {name}: sin resultados")
            continue
        print(
            f"  {name:<19} {total['neto']:+12} "
            f"{total['posiciones'] / partidas:12.2f} "
            f"{total['ganadas'] / partidas:5.0%} "
            f"{total['top3'] / partidas:6.0%} "
            f"{total['eliminaciones']:14} {total['timeouts']:9}"
        )
    print(f"\nResultados e historiales: {output}")

    if hubo_error:
        raise SystemExit("El benchmark tuvo mesas fallidas o resultados incompletos.")

    stack_path = write_stack_history(output, show_stacks)
    print(f"Fichas por mano: {stack_path}")


def main():
    args = parse_args()
    if args.hands <= 0 or args.seeds <= 0:
        raise SystemExit("--hands y --seeds deben ser mayores que cero")
    if not 1 <= args.rotations <= len(SEATS):
        raise SystemExit(f"--rotations debe estar entre 1 y {len(SEATS)}")

    rivals = SCENARIOS[args.scenario]
    bot_ids = {
        "aleatorio" if bot_id.startswith("aleatorio-") else bot_id
        for bot_id, _ in rivals
        if bot_id != "novato"
    }
    executables = [
        ARENA,
        *[
            BIN_DIR / (f"{bot_id}.exe" if sys.platform == "win32" else bot_id)
            for bot_id in sorted(bot_ids)
        ],
    ]
    for executable in executables:
        if not executable.is_file():
            raise SystemExit(
                f"No se encontro {executable}. Compila la arena y los bots desde {KIT_DIR}."
            )

    if args.output:
        output = args.output.resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = BOT_DIR / "benchmarks" / (
            f"6max-{args.scenario}-{timestamp}-seed-{args.seed}"
        )
    if output.exists():
        raise SystemExit(f"El directorio ya existe; no se sobrescribira: {output}")
    output.mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="poker-6max-") as temporal:
        config_path = Path(temporal) / "torneo.json"
        for seed_offset in range(args.seeds):
            seed = args.seed + seed_offset
            for rotation in range(args.rotations):
                result_dir = output / f"seed-{seed}" / f"rotacion-{rotation}"
                result_dir.mkdir(parents=True)
                config = build_config(
                    args.hands, seed, rotation, result_dir, args.scenario
                )
                config_path.write_text(
                    json.dumps(config, indent=2) + "\n", encoding="utf-8"
                )
                subprocess.run(
                    [str(ARENA), "validar", "-config", str(config_path)],
                    cwd=KIT_DIR,
                    check=True,
                )
                subprocess.run(
                    [str(ARENA), "correr", "-config", str(config_path)],
                    cwd=KIT_DIR,
                    check=True,
                )
    print_results(output, rivals, show_stacks=args.show_stacks)


if __name__ == "__main__":
    main()
