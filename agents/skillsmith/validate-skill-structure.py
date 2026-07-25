#!/usr/bin/env python3
"""
validate-skill-structure.py — ADAM-CICD
Validation complète de la structure des skills :
1. Chaque dossier de skill a un SKILL.md
2. Frontmatter YAML valide (name, description, tags)
3. Les wikilinks [[...]] pointent vers des pages existantes
4. Les tags sont dans la taxonomie définie

Usage : python3 validate-skill-structure.py [--dirs DIR1 DIR2 ...]
"""
import re
import sys
import yaml
import argparse
from pathlib import Path

# ── Couleurs ───────────────────────────────────────────────────────────────
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
NC = '\033[0m'

OK = f'{GREEN}[✓]{NC}'
WARN = f'{YELLOW}[!]{NC}'
ERR = f'{RED}[✗]{NC}'
INFO = f'{CYAN}[ADAM-VALIDATE]{NC}'

total_errors = 0
total_warnings = 0

def info(msg):    print(f'{INFO} {msg}')
def ok(msg):      print(f'{OK} {msg}')
def warn(msg):
    global total_warnings
    total_warnings += 1
    print(f'{WARN} {msg}')
def err(msg):
    global total_errors
    total_errors += 1
    print(f'{ERR} {msg}')

# ── Indexation du Wiki ────────────────────────────────────────────────────
def index_wiki_pages(wiki_dir):
    """Indexe toutes les pages wiki existantes (sans extension)"""
    pages = set()
    for f in Path(wiki_dir).rglob('*.md'):
        rel = str(f.relative_to(wiki_dir)).replace('.md', '')
        pages.add(rel)
    return pages

def index_taxonomy(wiki_dir, skill_dirs):
    """Indexe la taxonomie : catégories depuis le wiki + noms de dossiers"""
    taxonomy = set()

    # Depuis skills-categories.md : extraire les wikilinks [[...]]
    cat_file = Path(wiki_dir) / 'entities' / 'skills-categories.md'
    if cat_file.exists():
        content = cat_file.read_text(encoding='utf-8')
        for m in re.finditer(r'\[\[([a-zA-Z0-9_/-]+)\]\]', content):
            taxonomy.add(m.group(1))
        # Aussi les noms de catégories dans les tableaux
        for line in content.split('\n'):
            if line.startswith('|') and '|' in line[1:]:
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if parts and not parts[0].startswith('-'):
                    taxonomy.add(parts[0])

    # Depuis les dossiers skills
    for sd in skill_dirs:
        if sd.exists():
            for d in sd.iterdir():
                if d.is_dir():
                    taxonomy.add(d.name)
                    # Ajouter aussi le nom du skill (sanitized)
                    skill_md = d / 'SKILL.md'
                    if skill_md.exists():
                        try:
                            content = skill_md.read_text(encoding='utf-8')
                            data = list(yaml.safe_load_all(content))
                            if data and isinstance(data[0], dict):
                                if 'tags' in data[0] and isinstance(data[0]['tags'], list):
                                    for t in data[0]['tags']:
                                        taxonomy.add(t)
                        except Exception:
                            pass

    return taxonomy

# ── Validation 1 : Présence des SKILL.md ──────────────────────────────────
def check_skill_md_presence(skill_dirs):
    """Vérifie que chaque sous-dossier a un SKILL.md"""
    print(f'\n  {INFO} Étape 1 : Présence des SKILL.md')
    errors_before = total_errors
    for sd in skill_dirs:
        if not sd.exists():
            warn(f'Répertoire introuvable : {sd}')
            continue
        for d in sd.iterdir():
            if not d.is_dir():
                continue
            if not (d / 'SKILL.md').exists():
                err(f'SKILL.md manquant dans : {d}')
    ok('Vérification des dossiers terminée')

# ── Validation 2 : Frontmatter YAML ───────────────────────────────────────
def check_frontmatter_validation(skill_dirs):
    """Valide le frontmatter YAML de tous les SKILL.md"""
    print(f'\n  {INFO} Étape 2 : Frontmatter YAML')
    errors_before = total_errors
    for sd in skill_dirs:
        if not sd.exists():
            continue
        for skill_file in sd.rglob('SKILL.md'):
            dirname = skill_file.parent.name
            try:
                content = skill_file.read_text(encoding='utf-8')
            except Exception as e:
                err(f'Lecture impossible : {dirname} ({e})')
                continue

            if not content.startswith('---'):
                err(f'Pas de frontmatter (doit commencer par ---) : {dirname}')
                continue

            end_idx = content.find('---', 3)
            if end_idx == -1:
                err(f'Second --- introuvable : {dirname}')
                continue

            frontmatter = content[3:end_idx].strip()
            if not frontmatter:
                err(f'Frontmatter vide : {dirname}')
                continue

            try:
                data = yaml.safe_load(frontmatter)
            except yaml.YAMLError as e:
                err(f'YAML invalide : {dirname} ({e})')
                continue

            if not isinstance(data, dict):
                err(f'Frontmatter pas un dict : {dirname}')
                continue

            required = {'name', 'description', 'tags'}
            missing = required - set(data.keys())
            if missing:
                err(f'Champs manquants dans {dirname} : {missing}')
                continue

            if not isinstance(data.get('tags'), list):
                err(f'tags doit être une liste dans {dirname}')
                continue

            if not isinstance(data.get('name'), str) or not data['name'].strip():
                err(f'name doit être une chaîne non vide dans {dirname}')

    ok('Validation du frontmatter terminée')

# ── Validation 3 : Wikilinks ──────────────────────────────────────────────
def check_wikilinks(skill_dirs, wiki_pages):
    """Vérifie que les wikilinks [[...]] pointent vers des pages existantes"""
    # Ajouter les noms de dossiers skills comme pages valides
    skill_page_names = set()
    for sd in skill_dirs:
        if not sd.exists():
            continue
        for d in sd.iterdir():
            if d.is_dir():
                skill_page_names.add(d.name)
                # Format skills-xxx aussi
                skill_page_names.add(f'skills-{d.name}')

    all_pages = wiki_pages | skill_page_names

    print(f'\n  {INFO} Étape 3 : Wikilinks')
    errors_before = total_errors
    wiki_link_pattern = re.compile(r'\[\[([a-zA-Z0-9_/.-]+(?:#[a-zA-Z0-9_-]+)?)\]\]')

    for sd in skill_dirs:
        if not sd.exists():
            continue
        for skill_file in sd.rglob('SKILL.md'):
            dirname = skill_file.parent.name
            content = skill_file.read_text(encoding='utf-8')
            for m in wiki_link_pattern.finditer(content):
                link = m.group(1)
                # Nettoyer : enlever les pipes et après (alias)
                clean_link = link.split('|')[0].strip()
                if clean_link and clean_link not in all_pages:
                    warn(f'Wikilink orphelin dans "{dirname}" : [[{link}]] → page "{clean_link}" introuvable')

    ok('Vérification des wikilinks terminée')

# ── Validation 4 : Tags dans la taxonomie ─────────────────────────────────
def check_tags_taxonomy(skill_dirs, taxonomy):
    """Vérifie que les tags sont dans la taxonomie"""
    print(f'\n  {INFO} Étape 4 : Tags dans la taxonomie')
    errors_before = total_errors

    for sd in skill_dirs:
        if not sd.exists():
            continue
        for skill_file in sd.rglob('SKILL.md'):
            dirname = skill_file.parent.name
            try:
                content = skill_file.read_text(encoding='utf-8')
                data = list(yaml.safe_load_all(content))
                if data and isinstance(data[0], dict):
                    tags = data[0].get('tags', [])
                    if isinstance(tags, list):
                        for tag in tags:
                            if tag not in taxonomy:
                                warn(f'Tag "{tag}" non reconnu (skill: {dirname})')
            except Exception:
                pass

    ok('Vérification des tags terminée')

# ── Main ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Validation de structure des skills')
    parser.add_argument('--dirs', nargs='+', default=[
        '/home/aza/.hermes/hermes-agent/skills',
        '/home/aza/.hermes/skills',
    ], help='Répertoires de skills à valider')
    parser.add_argument('--wiki', default='/home/aza/wiki', help='Répertoire wiki')
    args = parser.parse_args()

    skill_dirs = [Path(d) for d in args.dirs]
    wiki_dir = Path(args.wiki)

    info('Indexation des pages wiki...')
    wiki_pages = index_wiki_pages(wiki_dir)
    ok(f'Pages wiki : {len(wiki_pages)}')

    info('Indexation de la taxonomie...')
    taxonomy = index_taxonomy(wiki_dir, skill_dirs)
    ok(f'Taxonomie : {len(taxonomy)} entrées')

    check_skill_md_presence(skill_dirs)
    check_frontmatter_validation(skill_dirs)
    check_wikilinks(skill_dirs, wiki_pages)
    check_tags_taxonomy(skill_dirs, taxonomy)

    # Bilan
    print(f'\n{"═" * 50}')
    print(f'{GREEN}  Validation terminée{NC}')
    print(f'{"═" * 50}')
    print(f'  Erreurs   : {total_errors}')
    print(f'  Avertissements : {total_warnings}')
    print()

    if total_errors > 0:
        print(f'{ERR} Certaines validations ont échoué')
        sys.exit(1)
    print(f'{OK} Toutes les validations sont passées')
    sys.exit(0)

if __name__ == '__main__':
    main()