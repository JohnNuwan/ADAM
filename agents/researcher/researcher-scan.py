#!/usr/bin/env python3
"""
ADAM Researcher — Vraie veille scientifique + analyse d'opportunités.

Améliorations:
  - Bug fix: urllib_quote défini avant usage
  - bioRxiv: fetch réel via API
  - arXiv: veille tech/IA/finance (API gratuite)
  - Scoring de valeur économique réelle ($ estimé)
  - Opportunités avec analyse de marché, pas juste "TBD"
  - Dé-duplication des findings déjà vus

Channels:
  - research:finding     → résultat de veille
  - research:opportunity → opportunité avec analyse de valeur
  - finance:report       → notifie le treasurer des opportunités high-value
"""

import sys
import os
import json
import re
import time
import hashlib
import argparse
import subprocess
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree

# ─── Config ───
RESEARCH_DIR = Path(os.path.expanduser("~/eva-adam-v2/research"))
FINDINGS_DIR = RESEARCH_DIR / "findings"
OPPORTUNITIES_DIR = RESEARCH_DIR / "opportunities"
SEEN_FILE = RESEARCH_DIR / "seen_findings.json"
LOG_DIR = Path(os.path.expanduser("~/eva-adam-v2/logs"))
LOG_FILE = LOG_DIR / "researcher-handler.log"
EVENT_BUS = os.path.expanduser("~/eva-adam-v2/publish.py")

for d in [FINDINGS_DIR, OPPORTUNITIES_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Sources ───
PUBMED_TOPICS = [
    "CRISPR gene editing", "mRNA vaccine", "AI drug discovery",
    "protein folding", "senolytic therapy", "organoid",
    "CAR-T cell therapy", "regenerative medicine",
]

BIORXIV_TOPICS = [
    "synthetic biology", "gene therapy", "biomarker",
]

ARXIV_TOPICS = [
    "reinforcement learning trading",
    "large language model efficiency",
    "federated learning healthcare",
    "quantum machine learning",
]

# ─── Scoring ───
HIGH_VALUE_KW = [
    "patent", "novel", "breakthrough", "first-in-class", "orphan drug",
    "fast track", "breakthrough therapy", "fda approval", "phase 3",
    "proof of concept", "preclinical", "lead compound", "drug candidate",
    "state-of-the-art", "sota", "outperform", "benchmark",
]

BUSINESS_KW = [
    "startup", "spin-off", "series a", "series b", "acquisition",
    "merger", "licensing deal", "exclusive license", "ipo",
    "commercialization", "market opportunity", "venture",
]

# Estimations de valeur ($ USD) par catégorie d'opportunité
VALUE_ESTIMATES = {
    "drug_candidate": (500_000, 50_000_000),    # lead compound → phase 1
    "fda_approval": (10_000_000, 1_000_000_000), # drug approved → market
    "breakthrough_therapy": (5_000_000, 500_000_000),
    "novel_method": (100_000, 10_000_000),        # méthode brevetable
    "sota_ai": (50_000, 5_000_000),              # IA SOTA → licensing/consulting
    "biomarker": (200_000, 20_000_000),           # diagnostic biomarker
    "default": (10_000, 1_000_000),
}


def log(level, msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [{level}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    if level == "ERROR":
        print(line, file=sys.stderr)
    else:
        print(line)


def publish(channel, payload):
    try:
        payload_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        result = subprocess.run(
            [sys.executable, EVENT_BUS, channel, payload_str],
            capture_output=True, text=True, timeout=15
        )
        return True
    except Exception as e:
        log("ERROR", f"Publish failed on {channel}: {e}")
        return False


def fetch_url(url, timeout=15):
    """Fetch URL avec urllib."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ADAM-Researcher/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log("WARN", f"Fetch failed {url[:80]}: {e}")
        return None


def quote(s):
    return urllib.parse.quote(s)


def load_seen():
    """Charge les IDs déjà vus pour dé-duplication."""
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen)[-500:], f)  # Garder max 500


# ─── Sources: PubMed ───
def scan_pubmed(topic, retmax=5):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    search_url = f"{base}esearch.fcgi?db=pubmed&retmax={retmax}&sort=date&term={quote(topic)}"
    data = fetch_url(search_url)
    if not data:
        return []
    pmids = re.findall(r"<Id>(\d+)</Id>", data)
    if not pmids:
        return []

    ids_str = ",".join(pmids)
    summary_url = f"{base}esummary.fcgi?db=pubmed&id={ids_str}&retmode=json"
    summary_data = fetch_url(summary_url)
    if not summary_data:
        return []

    results = []
    try:
        parsed = json.loads(summary_data)
        for pmid in pmids:
            entry = parsed.get("result", {}).get(pmid, {})
            if entry and entry.get("title"):
                results.append({
                    "source": "PubMed",
                    "id": f"PMID:{pmid}",
                    "title": entry.get("title", ""),
                    "authors": [a.get("name", "") for a in entry.get("authors", [])][:5],
                    "journal": entry.get("fulljournalname", ""),
                    "pubdate": entry.get("pubdate", ""),
                    "topic": topic,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
    except json.JSONDecodeError:
        pass
    return results


# ─── Sources: bioRxiv ───
def scan_biorxiv(topic, retmax=5):
    """Scan bioRxiv via API."""
    # api.biorxiv.org/details/biorxiv/{keyword}/{cursor}
    url = f"https://api.biorxiv.org/details/biorxiv/{quote(topic)}/0/{retmax}/json"
    data = fetch_url(url)
    if not data:
        return []

    results = []
    try:
        parsed = json.loads(data)
        collection = parsed.get("collection", [])
        for entry in collection:
            title = entry.get("title", "")
            if title:
                results.append({
                    "source": "bioRxiv",
                    "id": f"biorxiv:{entry.get('doi', entry.get('title', '')[:20])}",
                    "title": title,
                    "authors": entry.get("authors", "").split(";")[:5],
                    "journal": "bioRxiv (preprint)",
                    "pubdate": entry.get("date", ""),
                    "topic": topic,
                    "url": f"https://www.biorxiv.org/content/{entry.get('doi', '')}v1",
                })
    except json.JSONDecodeError:
        pass
    return results


# ─── Sources: arXiv ───
def scan_arxiv(topic, retmax=5):
    """Scan arXiv via API Atom XML."""
    url = f"http://export.arxiv.org/api/query?search_query=all:{quote(topic)}&max_results={retmax}&sortBy=submittedDate&sortOrder=descending"
    data = fetch_url(url)
    if not data:
        return []

    results = []
    try:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ElementTree.fromstring(data)
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns)
            summary = entry.find("atom:summary", ns)
            published = entry.find("atom:published", ns)
            link = entry.find("atom:id", ns)
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]

            if title is not None and title.text:
                results.append({
                    "source": "arXiv",
                    "id": f"arxiv:{link.text.split('/')[-1] if link is not None else ''}",
                    "title": " ".join(title.text.split()),
                    "authors": authors[:5],
                    "journal": "arXiv (preprint)",
                    "pubdate": published.text[:10] if published is not None else "",
                    "topic": topic,
                    "abstract": " ".join(summary.text.split()) if summary is not None else "",
                    "url": link.text if link is not None else "",
                })
    except ElementTree.ParseError as e:
        log("WARN", f"arXiv XML parse error: {e}")
    return results


# ─── Scoring & analyse de valeur ───
def score_finding(finding):
    """Score 0-100 + catégorie + estimation de valeur."""
    text = (finding.get("title", "") + " " + finding.get("abstract", "")).lower()
    score = 0
    reasons = []
    categories = []

    for kw in HIGH_VALUE_KW:
        if kw.lower() in text:
            score += 12
            reasons.append(f"HV: {kw}")
            if kw in ("drug candidate", "lead compound"):
                categories.append("drug_candidate")
            elif kw in ("fda approval", "phase 3"):
                categories.append("fda_approval")
            elif kw == "breakthrough therapy":
                categories.append("breakthrough_therapy")
            elif kw == "novel":
                categories.append("novel_method")
            elif kw in ("sota", "state-of-the-art", "outperform", "benchmark"):
                categories.append("sota_ai")
            elif kw == "biomarker":
                categories.append("biomarker")

    for kw in BUSINESS_KW:
        if kw.lower() in text:
            score += 15
            reasons.append(f"BG: {kw}")

    pubdate = finding.get("pubdate", "")
    if pubdate:
        try:
            year = int(pubdate[:4])
            if year >= 2025:
                score += 15
                reasons.append("Recent (2025+)")
            elif year >= 2024:
                score += 8
                reasons.append("2024")
        except ValueError:
            pass

    score = min(score, 100)

    # Estimation de valeur
    cat = categories[0] if categories else "default"
    low, high = VALUE_ESTIMATES.get(cat, VALUE_ESTIMATES["default"])
    # Ajuster par score
    value_factor = score / 100.0
    estimated_value_low = round(low * value_factor, 2)
    estimated_value_high = round(high * value_factor, 2)

    return {
        "score": score,
        "reasons": reasons,
        "category": cat,
        "estimated_value_usd": [estimated_value_low, estimated_value_high],
    }


def analyze_and_publish(finding, seen):
    """Analyse une finding et publie finding + éventuellement opportunité."""
    finding_id = hashlib.md5(
        f"{finding.get('id','')}:{finding.get('title','')}".encode()
    ).hexdigest()[:12]

    if finding_id in seen:
        return None
    seen.add(finding_id)

    analysis = score_finding(finding)
    finding["id"] = finding_id
    finding["score"] = analysis["score"]
    finding["score_reasons"] = analysis["reasons"]
    finding["value_category"] = analysis["category"]
    finding["estimated_value_usd"] = analysis["estimated_value_usd"]
    finding["scanned_at"] = datetime.now(timezone.utc).isoformat()

    # Sauvegarder
    finding_file = FINDINGS_DIR / f"finding-{finding_id}.json"
    with open(finding_file, "w") as f:
        json.dump(finding, f, indent=2, ensure_ascii=False)

    # Publier la finding
    publish("research:finding", {
        "agent": "adam-researcher",
        "finding_id": finding_id,
        "source": finding["source"],
        "topic": finding["topic"],
        "title": finding["title"],
        "score": analysis["score"],
        "reasons": analysis["reasons"],
        "value_category": analysis["category"],
        "estimated_value_usd": analysis["estimated_value_usd"],
        "timestamp": finding["scanned_at"],
    })

    # Opportunité si score ≥ 30
    if analysis["score"] >= 30:
        log("INFO", f"  🎯 Opportunité! score={analysis['score']} — {finding['title'][:60]}")
        log("INFO", f"     Valeur estimée: ${analysis['estimated_value_usd'][0]:,.0f} – ${analysis['estimated_value_usd'][1]:,.0f}")

        opp_data = {
            **finding,
            "type": f"opportunity:{analysis['category']}",
            "estimated_value_usd": analysis["estimated_value_usd"],
            "value_category": analysis["category"],
            "recommended_action": recommend_action(analysis["category"], analysis["score"]),
            "market_analysis": analyze_market(finding, analysis),
        }

        opp_file = OPPORTUNITIES_DIR / f"opp-{finding_id}.json"
        with open(opp_file, "w") as f:
            json.dump(opp_data, f, indent=2, ensure_ascii=False)

        publish("research:opportunity", {
            "agent": "adam-researcher",
            "finding_id": finding_id,
            "title": finding["title"],
            "source": finding["source"],
            "score": analysis["score"],
            "value_category": analysis["category"],
            "estimated_value_usd": analysis["estimated_value_usd"],
            "recommended_action": opp_data["recommended_action"],
            "market_analysis": opp_data["market_analysis"],
            "timestamp": finding["scanned_at"],
        })

        # Notifier le treasurer si haute valeur
        if analysis["score"] >= 50:
            publish("finance:report", {
                "agent": "adam-researcher",
                "type": "opportunity_notification",
                "title": finding["title"],
                "score": analysis["score"],
                "estimated_value_usd": analysis["estimated_value_usd"],
                "message": f"Opportunité haute valeur: {analysis['category']} — ${analysis['estimated_value_usd'][0]:,.0f}–${analysis['estimated_value_usd'][1]:,.0f}",
            })
    else:
        log("INFO", f"  📄 Finding score={analysis['score']} — {finding['title'][:60]}")

    return finding


def recommend_action(category, score):
    """Recommande une action selon la catégorie et le score."""
    actions = {
        "drug_candidate": "Vérifier brevetabilité → contacter un cabinet PI → évaluer licensing",
        "fda_approval": "Analyser le marché cible → estimer la taille du marché → identifier les concurrents",
        "breakthrough_therapy": "Suivre les essais cliniques → évaluer partenariats pharma",
        "novel_method": "Déposer un brevet provisionnel → publier ou garder secret commercial",
        "sota_ai": "Évaluer applications commerciales → prototype → pitch VCs",
        "biomarker": "Vérifier brevetabilité du test diagnostique → estimer marché clinique",
        "default": "Analyse approfondie requise",
    }
    return actions.get(category, actions["default"])


def analyze_market(finding, analysis):
    """Génère une mini-analyse de marché."""
    low, high = analysis["estimated_value_usd"]
    return {
        "tam_estimate": f"${low:,.0f} – ${high:,.0f}",
        "competition": "Inconnu — recherche concurrentielle requise",
        "time_to_market": "6-18 mois selon catégorie",
        "risk_level": "Élevé" if analysis["score"] < 50 else "Moyen",
        "monetization_paths": get_monetization_paths(analysis["category"]),
    }


def get_monetization_paths(category):
    paths = {
        "drug_candidate": ["Licensing pharma", "Spin-off biotech", "Partenariat recherche"],
        "fda_approval": ["Commercialisation directe", "Licensing exclusif", "Acquisition"],
        "novel_method": ["Brevet + licensing", "Consulting", "Spin-off tech"],
        "sota_ai": ["SaaS", "Consulting", "Licensing modèle", "Open-source + support"],
        "biomarker": ["Test diagnostique", "Licensing kit", "Partenariat labo"],
        "default": ["À déterminer"],
    }
    return paths.get(category, paths["default"])


# ─── Scan principal ───
def scan_all():
    """Scan toutes les sources."""
    seen = load_seen()
    all_findings = []

    # PubMed
    for topic in PUBMED_TOPICS:
        log("INFO", f"Scanning PubMed: '{topic}'...")
        results = scan_pubmed(topic)
        for r in results:
            f = analyze_and_publish(r, seen)
            if f:
                all_findings.append(f)
        time.sleep(1)  # Rate limit courtesy

    # bioRxiv
    for topic in BIORXIV_TOPICS:
        log("INFO", f"Scanning bioRxiv: '{topic}'...")
        results = scan_biorxiv(topic)
        for r in results:
            f = analyze_and_publish(r, seen)
            if f:
                all_findings.append(f)
        time.sleep(1)

    # arXiv
    for topic in ARXIV_TOPICS:
        log("INFO", f"Scanning arXiv: '{topic}'...")
        results = scan_arxiv(topic)
        for r in results:
            f = analyze_and_publish(r, seen)
            if f:
                all_findings.append(f)
        time.sleep(3)  # arXiv rate limit: 1 req / 3s

    save_seen(seen)

    log("INFO", f"=== Scan terminé: {len(all_findings)} nouvelles findings ===")
    high_score = [f for f in all_findings if f.get("score", 0) >= 30]
    log("INFO", f"  {len(high_score)} opportunités (score≥30)")

    return all_findings


# ─── Handler event bus ───
def handle_event(channel, payload_str):
    try:
        payload = json.loads(payload_str) if payload_str else {}
    except json.JSONDecodeError:
        payload = {}

    log("INFO", f"Event: channel={channel}")

    if channel == "evolution:code_review":
        log("INFO", "Code review noté — pas d'action recherche directe")

    elif channel == "research:finding":
        log("INFO", f"Finding reçue: {payload.get('title', 'unknown')[:60]}")

    elif channel == "research:opportunity":
        score = payload.get("score", 0)
        log("INFO", f"Opportunité reçue: score={score}")
        if score >= 50:
            publish("finance:report", {
                "agent": "adam-researcher",
                "type": "opportunity_notification",
                "title": payload.get("title", ""),
                "score": score,
                "estimated_value_usd": payload.get("estimated_value_usd", [0, 0]),
            })

    elif channel == "osint:finding":
        log("INFO", "OSINT finding reçue — corrélation possible")

    else:
        log("WARN", f"Canal non géré: {channel}")

    return True


# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description="ADAM Researcher — Veille scientifique + analyse opportunités")
    parser.add_argument("--scan", action="store_true", help="Scan toutes les sources")
    parser.add_argument("--event", nargs=2, metavar=("CHANNEL", "PAYLOAD"))
    parser.add_argument("--report", action="store_true", help="Affiche le bilan des findings")
    args = parser.parse_args()

    if args.scan:
        log("INFO", "=== Début scan veille scientifique ===")
        findings = scan_all()
        log("INFO", f"=== Scan terminé: {len(findings)} nouvelles findings ===")

    elif args.report:
        # Bilan
        all_f = list(FINDINGS_DIR.glob("*.json"))
        all_o = list(OPPORTUNITIES_DIR.glob("*.json"))
        print(f"📊 Researcher Bilan:")
        print(f"  Findings totales: {len(all_f)}")
        print(f"  Opportunités: {len(all_o)}")
        if all_o:
            print(f"\n  Top opportunités:")
            opps = []
            for f in all_o:
                try:
                    with open(f) as fh:
                        d = json.load(fh)
                    opps.append((d.get("score", 0), d.get("title", "?"), d.get("estimated_value_usd", [0,0])))
                except Exception:
                    pass
            opps.sort(reverse=True)
            for score, title, val in opps[:5]:
                print(f"    [{score}] {title[:60]} → ${val[0]:,.0f}–${val[1]:,.0f}")

    elif args.event:
        channel, payload = args.event
        handle_event(channel, payload)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
