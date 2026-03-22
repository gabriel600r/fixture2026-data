#!/usr/bin/env python3
"""
Fixture Mundial 2026 — Script de actualización de resultados.

Uso:
  python3 update.py add 1 2 1          # Partido 1: local 2 - visitante 1
  python3 update.py add 1 2 1 2 0 0    # Cargar varios de una vez
  python3 update.py remove 1            # Quitar resultado del partido 1
  python3 update.py list                # Ver todos los resultados cargados
  python3 update.py push                # Pushear a GitHub
  python3 update.py interactive         # Modo interactivo

IDs de partidos:
  1-72    Fase de grupos (12 grupos × 6 partidos)
  73-88   Dieciseisavos de final
  89-96   Octavos de final
  97-100  Cuartos de final
  101-102 Semifinales
  103     Tercer puesto
  104     Final
"""

import json
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "results.json"
MAX_MATCH_ID = 104


def load_results():
    with open(RESULTS_FILE, "r") as f:
        return json.load(f)


def save_results(data):
    data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Guardado. {len(data['results'])} resultados en total.")


def add_result(data, match_id, home, away):
    if match_id < 1 or match_id > MAX_MATCH_ID:
        print(f"  Error: ID {match_id} fuera de rango (1-{MAX_MATCH_ID})")
        return False
    if home < 0 or away < 0:
        print(f"  Error: goles no pueden ser negativos")
        return False

    # Update if exists, otherwise add
    for r in data["results"]:
        if r["id"] == match_id:
            old = f"{r['home']}-{r['away']}"
            r["home"] = home
            r["away"] = away
            print(f"  Partido {match_id}: {old} -> {home}-{away} (actualizado)")
            return True

    data["results"].append({"id": match_id, "home": home, "away": away})
    data["results"].sort(key=lambda r: r["id"])
    print(f"  Partido {match_id}: {home}-{away} (nuevo)")
    return True


def remove_result(data, match_id):
    before = len(data["results"])
    data["results"] = [r for r in data["results"] if r["id"] != match_id]
    if len(data["results"]) < before:
        print(f"  Partido {match_id}: eliminado")
        return True
    else:
        print(f"  Partido {match_id}: no encontrado")
        return False


def list_results(data):
    if not data["results"]:
        print("No hay resultados cargados.")
        return

    print(f"Última actualización: {data['updated']}")
    print(f"Total: {len(data['results'])} resultados\n")
    print(f"{'ID':>4}  {'Local':>5}  {'Visit':>5}  {'Fase'}")
    print("-" * 35)
    for r in sorted(data["results"], key=lambda x: x["id"]):
        stage = get_stage(r["id"])
        print(f"{r['id']:>4}  {r['home']:>5}  {r['away']:>5}  {stage}")


def get_stage(match_id):
    if match_id <= 72:
        return "Grupos"
    elif match_id <= 88:
        return "Dieciseisavos"
    elif match_id <= 96:
        return "Octavos"
    elif match_id <= 100:
        return "Cuartos"
    elif match_id <= 102:
        return "Semifinal"
    elif match_id == 103:
        return "3er puesto"
    elif match_id == 104:
        return "Final"
    return "?"


def git_push():
    try:
        subprocess.run(["git", "add", "results.json"], check=True)
        count = len(load_results()["results"])
        msg = f"Actualizar resultados ({count} partidos)"
        subprocess.run(["git", "commit", "-m", msg], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("\nPusheado a GitHub exitosamente.")
    except subprocess.CalledProcessError as e:
        print(f"\nError en git: {e}")


def interactive():
    print("=== Fixture Mundial 2026 — Modo interactivo ===")
    print("Comandos: add <id> <local> <visit> | remove <id> | list | push | exit\n")

    data = load_results()

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        if cmd == "exit" or cmd == "quit":
            break
        elif cmd == "list":
            list_results(data)
        elif cmd == "push":
            save_results(data)
            git_push()
        elif cmd == "add":
            if len(parts) < 4 or (len(parts) - 1) % 3 != 0:
                print("Uso: add <id> <local> <visit> [<id> <local> <visit> ...]")
                continue
            changed = False
            for i in range(1, len(parts), 3):
                try:
                    mid, h, a = int(parts[i]), int(parts[i + 1]), int(parts[i + 2])
                    if add_result(data, mid, h, a):
                        changed = True
                except (ValueError, IndexError):
                    print(f"  Error parseando: {parts[i:i+3]}")
            if changed:
                save_results(data)
        elif cmd == "remove":
            if len(parts) < 2:
                print("Uso: remove <id>")
                continue
            try:
                mid = int(parts[1])
                if remove_result(data, mid):
                    save_results(data)
            except ValueError:
                print("ID inválido")
        else:
            print(f"Comando desconocido: {cmd}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1].lower()

    if cmd == "interactive":
        interactive()
        return

    data = load_results()

    if cmd == "list":
        list_results(data)

    elif cmd == "add":
        args = sys.argv[2:]
        if len(args) < 3 or len(args) % 3 != 0:
            print("Uso: python3 update.py add <id> <local> <visit> [<id> <local> <visit> ...]")
            return
        changed = False
        for i in range(0, len(args), 3):
            try:
                mid, h, a = int(args[i]), int(args[i + 1]), int(args[i + 2])
                if add_result(data, mid, h, a):
                    changed = True
            except (ValueError, IndexError):
                print(f"  Error parseando: {args[i:i+3]}")
        if changed:
            save_results(data)

    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("Uso: python3 update.py remove <id>")
            return
        try:
            mid = int(sys.argv[2])
            if remove_result(data, mid):
                save_results(data)
        except ValueError:
            print("ID inválido")

    elif cmd == "push":
        git_push()

    else:
        print(f"Comando desconocido: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
