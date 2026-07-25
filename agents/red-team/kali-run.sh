#!/usr/bin/env bash
# Wrapper pour exécuter des commandes dans le conteneur Kali
# Usage: ~/scripts/kali-run.sh <commande...>
# Exemple: ~/scripts/kali-run.sh nmap -sV 192.168.1.5
docker exec -it kali-pentest "$@"
