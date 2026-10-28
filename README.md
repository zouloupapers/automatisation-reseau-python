# Automatisation réseau avec Python et Netmiko

> **EN** — Small Python CLI built on Netmiko to automate Cisco IOS devices from a YAML inventory: back up running configurations and deploy VLANs to switches (with a dry-run mode). Credentials are read from environment variables, never stored in the code.

Outil en ligne de commande qui relie mon cours **Python (Cisco NetAcad)** et le chapitre automatisation du **CCNA3**. Il remplace des tâches répétitives faites à la main équipement par équipement.

## Fonctionnalités

| Commande | Ce qu'elle fait |
|---|---|
| `backup` | Se connecte en SSH à chaque équipement de l'inventaire et enregistre sa `running-config` dans `backups/NOM_date.cfg` |
| `vlans` | Crée ou renomme sur les commutateurs les VLAN définis dans `inventory.yaml` |
| `vlans --dry-run` | Affiche les commandes qui seraient envoyées, sans se connecter |

- Inventaire **YAML** validé au chargement (champs obligatoires, numéros et noms de VLAN).
- Filtre `--hosts` pour cibler un ou plusieurs équipements.
- Gestion des erreurs de connexion : un équipement injoignable n'arrête pas les autres, le code de sortie signale l'échec.
- Identifiants lus dans un fichier `.env` **ignoré par Git**.

## Installation

```bash
git clone https://github.com/zouloupapers/automatisation-reseau-python.git
cd automatisation-reseau-python
python -m venv .venv
# Windows : .venv\Scripts\activate    Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # puis renseigner NET_USERNAME, NET_PASSWORD, NET_SECRET
```

## Utilisation

```bash
# Voir les commandes VLAN sans toucher aux équipements
python netauto.py vlans --dry-run

# Déployer les VLAN sur SW1 et enregistrer la configuration
python netauto.py vlans --hosts SW1 --save

# Sauvegarder la configuration de tous les équipements
python netauto.py backup
```

Exemple de sortie :

```
[OK]    R1-EDGE -> backups/R1-EDGE_20261105-101500.cfg
[OK]    R2-CORE -> backups/R2-CORE_20261105-101500.cfg
[ECHEC] SW1 (192.168.99.2) : NetmikoTimeoutException

2/3 sauvegarde(s) reussie(s).
```

## Environnement de test

L'inventaire reprend les adresses du labo [lab-reseau-entreprise](https://github.com/zouloupapers/lab-reseau-entreprise). Packet Tracer n'accepte pas de connexion SSH venant de l'extérieur : pour tester sur de vrais IOS, il faut un émulateur (**GNS3**, **EVE-NG**, **Cisco CML**) ou un sandbox **Cisco DevNet**. Les équipements doivent avoir SSH activé et un compte local.

## Sécurité

- Aucun identifiant dans le code ni dans l'inventaire : tout passe par `.env`.
- `backups/` et `*.cfg` sont ignorés par Git, car une configuration exportée peut contenir des secrets.
- Connexions en SSH uniquement.

## Structure

```
automatisation-reseau-python/
├── netauto.py         # outil en ligne de commande
├── inventory.yaml     # équipements et VLAN
├── requirements.txt
├── .env.example       # modèle de fichier d'identifiants
└── .gitignore
```

## Feuille de route

- [ ] Tests unitaires avec `pytest` (validation de l'inventaire, génération des commandes)
- [ ] Commande `audit` : lire `show ip interface brief` avec TextFSM et signaler les interfaces down
- [ ] Comparaison entre deux sauvegardes (diff de configuration)
- [ ] Version équivalente avec **Ansible**

## Auteur

**Bien De Grace KABITOU ONDONGO** — étudiant en 3ᵉ année de licence Ingénierie des réseaux et systèmes, Université Centrale (Tunis) · CCNA1 & CCNA2.
Je recherche un **stage de fin d'études du 1ᵉʳ février au 31 mars 2027**.

Licence : [MIT](LICENSE)
