#!/usr/bin/env python3
"""netauto - petits outils d'automatisation reseau avec Netmiko.

Commandes :
  backup   sauvegarde la running-config de chaque equipement de l'inventaire
  vlans    cree (ou renomme) sur les commutateurs les VLAN definis dans l'inventaire

Les identifiants sont lus dans les variables d'environnement (ou un fichier .env) :
  NET_USERNAME, NET_PASSWORD et, si besoin, NET_SECRET (mot de passe enable).
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

DEFAULT_INVENTORY = "inventory.yaml"


# --------------------------------------------------------------------------
# Inventaire et identifiants
# --------------------------------------------------------------------------
def load_inventory(path: str) -> dict:
    """Charge et valide le fichier d'inventaire YAML."""
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except FileNotFoundError:
        sys.exit(f"Inventaire introuvable : {path}")

    devices = data.get("devices") or []
    for device in devices:
        for key in ("name", "host", "device_type"):
            if key not in device:
                sys.exit(f"Equipement incomplet dans l'inventaire (champ '{key}' manquant) : {device}")

    for vlan in data.get("vlans") or []:
        vlan_id = vlan.get("id")
        name = str(vlan.get("name", ""))
        if not isinstance(vlan_id, int) or not 2 <= vlan_id <= 4094 or vlan_id in range(1002, 1006):
            sys.exit(f"Identifiant de VLAN invalide : {vlan_id}")
        if not name or " " in name or len(name) > 32:
            sys.exit(f"Nom de VLAN invalide pour le VLAN {vlan_id} : '{name}' (32 caracteres max, sans espace)")

    data["devices"] = devices
    return data


def select_devices(devices: list[dict], names: list[str] | None, role: str | None = None) -> list[dict]:
    """Filtre les equipements par nom (--hosts) et/ou par role."""
    selected = devices
    if role:
        selected = [d for d in selected if d.get("role") == role]
    if names:
        wanted = {n.lower() for n in names}
        selected = [d for d in selected if d["name"].lower() in wanted]
    return selected


def get_credentials() -> dict:
    """Lit les identifiants dans l'environnement : jamais dans le code ni dans Git."""
    load_dotenv()
    username = os.getenv("NET_USERNAME")
    password = os.getenv("NET_PASSWORD")
    if not username or not password:
        sys.exit("Identifiants manquants : definir NET_USERNAME et NET_PASSWORD (voir .env.example).")
    return {"username": username, "password": password, "secret": os.getenv("NET_SECRET", "")}


def connect(device: dict, creds: dict, timeout: int):
    """Ouvre une session SSH vers l'equipement et passe en mode enable si besoin."""
    from netmiko import ConnectHandler  # import tardif : --dry-run fonctionne sans connexion

    conn = ConnectHandler(
        device_type=device["device_type"],
        host=device["host"],
        port=device.get("port", 22),
        username=creds["username"],
        password=creds["password"],
        secret=creds["secret"],
        conn_timeout=timeout,
    )
    if creds["secret"] and not conn.check_enable_mode():
        conn.enable()
    return conn


def connection_errors() -> tuple:
    from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

    return (NetmikoTimeoutException, NetmikoAuthenticationException, OSError)


# --------------------------------------------------------------------------
# Commande : backup
# --------------------------------------------------------------------------
def cmd_backup(inventory: dict, args: argparse.Namespace) -> int:
    devices = select_devices(inventory["devices"], args.hosts)
    if not devices:
        print("Aucun equipement selectionne.")
        return 1

    creds = get_credentials()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    failures = 0

    for device in devices:
        try:
            with connect(device, creds, args.timeout) as conn:
                config = conn.send_command("show running-config")
        except connection_errors() as exc:
            failures += 1
            print(f"[ECHEC] {device['name']} ({device['host']}) : {exc.__class__.__name__}")
            continue

        target = out_dir / f"{device['name']}_{stamp}.cfg"
        target.write_text(config, encoding="utf-8")
        print(f"[OK]    {device['name']} -> {target}")

    print(f"\n{len(devices) - failures}/{len(devices)} sauvegarde(s) reussie(s).")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# Commande : vlans
# --------------------------------------------------------------------------
def vlan_commands(vlans: list[dict]) -> list[str]:
    commands: list[str] = []
    for vlan in sorted(vlans, key=lambda v: v["id"]):
        commands += [f"vlan {vlan['id']}", f" name {vlan['name']}"]
    return commands


def cmd_vlans(inventory: dict, args: argparse.Namespace) -> int:
    vlans = inventory.get("vlans") or []
    if not vlans:
        print("Aucun VLAN defini dans l'inventaire.")
        return 1

    switches = select_devices(inventory["devices"], args.hosts, role="switch")
    if not switches:
        print("Aucun commutateur (role: switch) selectionne.")
        return 1

    commands = vlan_commands(vlans)

    if args.dry_run:
        for switch in switches:
            print(f"--- {switch['name']} ({switch['host']}) : commandes qui seraient envoyees ---")
            print("\n".join(commands))
            print()
        return 0

    creds = get_credentials()
    failures = 0
    for switch in switches:
        try:
            with connect(switch, creds, args.timeout) as conn:
                output = conn.send_config_set(commands)
                if args.save:
                    output += "\n" + conn.save_config()
        except connection_errors() as exc:
            failures += 1
            print(f"[ECHEC] {switch['name']} ({switch['host']}) : {exc.__class__.__name__}")
            continue
        print(f"[OK]    {switch['name']} : {len(vlans)} VLAN appliques")
        if args.verbose:
            print(output)

    return 1 if failures else 0


# --------------------------------------------------------------------------
# Point d'entree
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    # Options communes, acceptees apres chaque sous-commande
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-i", "--inventory", default=DEFAULT_INVENTORY, help="fichier d'inventaire YAML")
    common.add_argument("--hosts", nargs="+", metavar="NOM", help="limiter a certains equipements")
    common.add_argument("--timeout", type=int, default=10, help="delai de connexion en secondes (defaut : 10)")

    parser = argparse.ArgumentParser(description="Automatisation reseau avec Netmiko")
    sub = parser.add_subparsers(dest="command", required=True)

    backup = sub.add_parser("backup", parents=[common], help="sauvegarder les running-config")
    backup.add_argument("-o", "--output", default="backups", help="dossier de sortie (defaut : backups/)")
    backup.set_defaults(func=cmd_backup)

    vlans = sub.add_parser("vlans", parents=[common], help="deployer les VLAN sur les commutateurs")
    vlans.add_argument("--dry-run", action="store_true", help="afficher les commandes sans se connecter")
    vlans.add_argument("--save", action="store_true", help="enregistrer la configuration (write memory)")
    vlans.add_argument("-v", "--verbose", action="store_true", help="afficher la sortie des equipements")
    vlans.set_defaults(func=cmd_vlans)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inventory = load_inventory(args.inventory)
    return args.func(inventory, args)


if __name__ == "__main__":
    sys.exit(main())
