#!/usr/bin/env python3
"""Compara Michi Novato con Gato Darwin usando la arena local."""

import argparse
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
DARWIN = BIN_DIR / ("darwin.exe" if sys.platform == "win32" else "darwin")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Mide Michi Novato contra Gato Darwin con posiciones alternadas."
    )
    parser.add_argument(
        "--hands",
        type=int,
        default=200,
        help="manos por posicion (default: 200; se juegan el doble con ida y vuelta)",
    )
    parser.add_argument("--seed", type=int, default=20261119, help="semilla de la arena")
    parser.add_argument(
        "--output",
        type=Path,
        help="directorio nuevo para guardar resultados e historial",
    )
    return parser.parse_args()


def build_config(hands, seed, output):
    return {
        "nombre": f"novato-vs-darwin-{hands}x2-seed-{seed}",
        "formato": "round-robin",
        "puntuacion": "neto",
        "manos_por_enfrentamiento": hands,
        "ida_y_vuelta": True,
        "reponer_stack": True,
        "semilla": seed,
        "paralelismo": 1,
        "penalizacion_timeout": 0,
        "guardar_historial": True,
        "salida": str(output),
        "mesa": {
            "ciega_chica": 10,
            "ciega_grande": 20,
            "stack": 4000,
            "timeout_ms": 5000,
            "espera_jugadores_ms": 15000,
        },
        "participantes": [
            {
                "id": "novato",
                "nombre": "Michi Novato",
                "comando": [sys.executable, str(BOT_DIR / "bot.py"), "-silencioso"],
                "directorio": str(KIT_DIR),
            },
            {
                "id": "darwin",
                "nombre": "Gato Darwin",
                "comando": [
                    str(DARWIN),
                    "-silencioso",
                    "-semilla",
                    str(seed),
                ],
                "directorio": str(KIT_DIR),
            },
        ],
    }


def print_results(output):
    path = output / "enfrentamientos.jsonl"
    resultados = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    totales = {
        jugador: {"neto": 0, "manos": 0, "timeouts": 0}
        for jugador in ("novato", "darwin")
    }
    hubo_error = False

    print("\nResultados por posicion:")
    for resultado in resultados:
        print(f"  {resultado['id']}:")
        if resultado.get("error"):
            hubo_error = True
            print(f"    ERROR: {resultado['error']}")
            continue
        for puesto in resultado["puestos"]:
            jugador = totales[puesto["id_participante"]]
            jugador["neto"] += puesto["neto"]
            jugador["manos"] += puesto["manos_jugadas"]
            jugador["timeouts"] += puesto["timeouts"]
            print(
                f"    {puesto['nombre']}: {puesto['neto']:+} fichas, "
                f"{puesto['manos_jugadas']} manos, {puesto['timeouts']} timeouts"
            )

    print("\nBalance total:")
    for jugador, valores in totales.items():
        manos = valores["manos"]
        bb100 = valores["neto"] * 100 / (20 * manos) if manos else 0
        print(
            f"  {jugador}: {valores['neto']:+} fichas, "
            f"{bb100:+.1f} BB/100, {valores['timeouts']} timeouts"
        )
    print(f"Historial y configuracion: {output}")

    if hubo_error:
        raise SystemExit("El benchmark tuvo enfrentamientos fallidos; revisar los errores.")


def main():
    args = parse_args()
    if args.hands <= 0:
        raise SystemExit("--hands debe ser mayor que cero")
    for executable in (ARENA, DARWIN):
        if not executable.is_file():
            raise SystemExit(
                f"No se encontro {executable}. Compila la arena y Darwin desde {KIT_DIR}."
            )

    if args.output:
        output = args.output.resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = BOT_DIR / "benchmarks" / f"darwin-{timestamp}-seed-{args.seed}"
    if output.exists():
        raise SystemExit(f"El directorio ya existe; no se sobrescribira: {output}")
    output.mkdir(parents=True)

    config = build_config(args.hands, args.seed, output)
    with tempfile.TemporaryDirectory(prefix="poker-benchmark-") as temporal:
        config_path = Path(temporal) / "torneo.json"
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
    print_results(output)


if __name__ == "__main__":
    main()
