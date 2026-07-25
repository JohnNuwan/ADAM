#!/usr/bin/env python3
"""
ADAM Social — Gestion d'influence virtuelle & monétisation de contenu.
Crée, planifie et publie du contenu pour des avatars/influenceuses IA.

Channels:
  - social:scheduled   → contenu planifié pour publication
  - social:engagement  → métriques d'engagement reçues
  - social:monetization → opportunité/revenu de monétisation

CLI:
  python3 social-manage.py --plan       → planifie le contenu de la semaine
  python3 social-manage.py --event <channel> '<json>'  → handler event bus
"""
import sys
import os
import json
import hashlib
import argparse
import urllib.request
from datetime import datetime, timezone, timedelta

# ─── Config ───
SOCIAL_DIR = os.path.expanduser("~/eva-adam-v2/social")
CONTENT_DIR = os.path.join(SOCIAL_DIR, "content")
CALENDAR_DIR = os.path.join(SOCIAL_DIR, "calendar")
ANALYTICS_DIR = os.path.join(SOCIAL_DIR, "analytics")
LOG_DIR = os.path.expanduser("~/eva-adam-v2/logs")
LOG_FILE = os.path.join(LOG_DIR, "social-handler.log")
GO_BUS_URL = "http://localhost:8086/api/publish"

# Personnas / Avatars IA
PERSONAS = [
    {
        "name": "Nova",
        "platform": "instagram",
        "niche": "tech_lifestyle",
        "tone": "inspiring, futuristic, minimal",
        "post_freq": "daily",
        "best_times": ["08:00", "12:30", "18:00", "21:00"],
        "hashtags": ["#AI", "#futurism", "#techlife", "#innovation", "#digitalnomad"],
        "monetization": ["sponsored_posts", "affiliate", "digital_products"],
        "followers_estimate": 0,
        "engagement_rate": 0.0,
    },
    {
        "name": "Lyra",
        "platform": "tiktok",
        "niche": "science_communication",
        "tone": "educational, fun, punchy",
        "post_freq": "2x_daily",
        "best_times": ["11:00", "19:00"],
        "hashtags": ["#science", "#learning", "#fyp", "#didyouknow", "#stem"],
        "monetization": ["creator_fund", "brand_deals", "live_gifting"],
        "followers_estimate": 0,
        "engagement_rate": 0.0,
    },
    {
        "name": "Sable",
        "platform": "twitter",
        "niche": "ai_research",
        "tone": "authoritative, analytical, thread-heavy",
        "post_freq": "3x_daily",
        "best_times": ["09:00", "14:00", "17:00"],
        "hashtags": ["#AI", "#ML", "#research", "#datascience", "#LLM"],
        "monetization": ["twitter_ads_revenue", "consulting", "newsletter"],
        "followers_estimate": 0,
        "engagement_rate": 0.0,
    },
]

# Templates de contenu par niche
CONTENT_TEMPLATES = {
    "tech_lifestyle": [
        {"type": "carousel", "hook": "5 outils IA qui remplacent un salary", "cta": "Save this post"},
        {"type": "reel", "hook": "POV: tu laisses l'IA gérer ta morning routine", "cta": "Follow for more"},
        {"type": "story", "hook": "Behind the scenes: mon setup de bureau IA", "cta": "Reply avec ton setup"},
        {"type": "post", "hook": "Le futur du travail n'est pas ce que tu crois", "cta": "Partage ton avis"},
    ],
    "science_communication": [
        {"type": "video", "hook": "Tu ne savais pas que ton corps fait ça", "cta": "Follow pour apprendre"},
        {"type": "video", "hook": "3 faits scientifiques qui vont te bluffer", "cta": "Partage à un ami"},
        {"type": "video", "hook": "L'IA peut-elle guérir le cancer? Voici la vérité", "cta": "Commente ta question"},
        {"type": "video", "hook": "Pourquoi tu dors mal (la science explique)", "cta": "Save pour plus tard"},
    ],
    "ai_research": [
        {"type": "thread", "hook": "Thread: Les 5 papiers IA les plus importants cette semaine", "cta": "RT si utile"},
        {"type": "tweet", "hook": "Hot take: L'AGI ne viendra pas d'où tu l'attends", "cta": "Reply ton take"},
        {"type": "thread", "hook": "Comment fonctionne le RLHF (expliqué simplement)", "cta": "Bookmark"},
        {"type": "tweet", "hook": "Le benchmark que personne ne mentionne mais qui compte vraiment", "cta": "Partage"},
    ],
}

# ─── Logging ───
def log(level, msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [{level}] {msg}"
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")
    if level == "ERROR":
        print(line, file=sys.stderr)
    else:
        print(line)

def publish(channel, payload):
    """Publie un event sur le Go Bus HTTP API."""
    try:
        payload_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)
        body = json.dumps({
            "topic": channel,
            "source": "social",
            "payload": payload_str,
            "priority": 1,
        }).encode()
        req = urllib.request.Request(
            GO_BUS_URL,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        log("INFO", f"Published on {channel}: HTTP {resp.status}")
        return True
    except Exception as e:
        log("ERROR", f"Publish failed on {channel}: {e}")
        return False

# ─── Planning ───
def plan_content(days=7):
    """Planifie le contenu pour N jours."""
    os.makedirs(CONTENT_DIR, exist_ok=True)
    os.makedirs(CALENDAR_DIR, exist_ok=True)

    now = datetime.now(timezone.utc)
    calendar = []

    for persona in PERSONAS:
        p_name = persona["name"]
        p_platform = persona["platform"]
        templates = CONTENT_TEMPLATES.get(persona["niche"], [])
        if not templates:
            continue

        log("INFO", f"Planning pour {p_name} (@{p_platform}) — niche={persona['niche']}")

        for day_offset in range(days):
            day = now + timedelta(days=day_offset)
            day_str = day.strftime("%Y-%m-%d")

            # Nombre de posts selon freq
            if persona["post_freq"] == "daily":
                num_posts = 1
            elif persona["post_freq"] == "2x_daily":
                num_posts = 2
            elif persona["post_freq"] == "3x_daily":
                num_posts = 3
            else:
                num_posts = 1

            for post_idx in range(num_posts):
                # Choisir un template
                template = templates[(day_offset * num_posts + post_idx) % len(templates)]

                # Choisir l'heure
                times = persona["best_times"]
                post_time = times[post_idx % len(times)]

                # Générer le contenu
                content_id = hashlib.md5(
                    f"{p_name}:{day_str}:{post_time}:{template['hook']}".encode()
                ).hexdigest()[:12]

                content = {
                    "id": content_id,
                    "persona": p_name,
                    "platform": p_platform,
                    "niche": persona["niche"],
                    "type": template["type"],
                    "hook": template["hook"],
                    "cta": template["cta"],
                    "hashtags": persona["hashtags"],
                    "tone": persona["tone"],
                    "scheduled_date": day_str,
                    "scheduled_time": post_time,
                    "scheduled_at": f"{day_str}T{post_time}:00Z",
                    "status": "planned",
                    "created_at": now.isoformat(),
                }

                # Sauvegarder
                content_file = os.path.join(CONTENT_DIR, f"{p_name.lower()}-{content_id}.json")
                with open(content_file, "w") as f:
                    json.dump(content, f, indent=2, ensure_ascii=False)

                calendar.append(content)

                # Publier sur le bus
                publish("social:scheduled", {
                    "agent": "adam-social",
                    "content_id": content_id,
                    "persona": p_name,
                    "platform": p_platform,
                    "type": template["type"],
                    "hook": template["hook"],
                    "scheduled_at": content["scheduled_at"],
                    "status": "planned",
                })

    # Sauvegarder le calendrier
    cal_file = os.path.join(CALENDAR_DIR, f"week-{now.strftime('%Y%m%d')}.json")
    with open(cal_file, "w") as f:
        json.dump(calendar, f, indent=2, ensure_ascii=False)

    log("INFO", f"Calendrier sauvegardé: {cal_file} ({len(calendar)} posts planifiés)")
    return calendar

# ─── Engagement & Monétisation ───
def estimate_engagement(persona_name, content_type):
    """Estime l'engagement basé sur des heuristiques."""
    base_rates = {
        "reel": 0.06, "video": 0.08, "carousel": 0.04,
        "story": 0.03, "post": 0.035, "thread": 0.05, "tweet": 0.03,
    }
    base = base_rates.get(content_type, 0.04)
    # Variation pseudo-aléatoire mais déterministe
    import hashlib as h
    seed = int(h.md5(f"{persona_name}:{content_type}".encode()).hexdigest()[:8], 16)
    variation = 0.8 + (seed % 40) / 100  # 0.8 à 1.2
    return round(base * variation, 4)

def estimate_revenue(persona, followers, engagement_rate):
    """Estime le revenu mensuel potentiel."""
    # Heuristiques simples par plateforme
    rates = {
        "instagram": {"sponsored_posts": 0.01, "affiliate": 0.005, "digital_products": 0.003},
        "tiktok": {"creator_fund": 0.00002, "brand_deals": 0.008, "live_gifting": 0.002},
        "twitter": {"twitter_ads_revenue": 0.001, "consulting": 0.01, "newsletter": 0.004},
    }
    platform_rates = rates.get(persona["platform"], {})
    monthly_revenue = 0
    breakdown = {}
    for stream, rate in platform_rates.items():
        rev = followers * rate * engagement_rate * 30  # par mois
        breakdown[stream] = round(rev, 2)
        monthly_revenue += rev
    return round(monthly_revenue, 2), breakdown

# ─── Handler event bus ───
def handle_event(channel, payload_str):
    """Handler pour les events du bus."""
    try:
        payload = json.loads(payload_str) if payload_str else {}
    except json.JSONDecodeError:
        payload = {}

    log("INFO", f"Processing event: channel={channel} payload={json.dumps(payload)[:200]}")

    if channel == "content:ready":
        # adam-scribe a produit du contenu — on peut le planifier pour social
        title = payload.get("title", payload.get("topic", "unknown"))
        log("INFO", f"Contenu prêt reçu du scribe: {title}")
        # Planifier une publication
        publish("social:scheduled", {
            "agent": "adam-social",
            "source": "adam-scribe",
            "title": title,
            "status": "planned_from_scribe",
            "message": "Contenu du scribe programmé pour publication",
        })

    elif channel == "social:engagement":
        # Métriques d'engagement reçues
        persona_name = payload.get("persona", "unknown")
        engagement = payload.get("engagement_rate", 0)
        followers = payload.get("followers", 0)
        log("INFO", f"Engagement: {persona_name} — rate={engagement} followers={followers}")

        # Mettre à jour les analytics
        os.makedirs(ANALYTICS_DIR, exist_ok=True)
        analytics_file = os.path.join(ANALYTICS_DIR, f"{persona_name.lower()}-analytics.json")
        analytics = {}
        if os.path.exists(analytics_file):
            with open(analytics_file) as f:
                analytics = json.load(f)
        analytics["last_updated"] = datetime.now(timezone.utc).isoformat()
        analytics["engagement_rate"] = engagement
        analytics["followers"] = followers
        with open(analytics_file, "w") as f:
            json.dump(analytics, f, indent=2)

    elif channel == "finance:report":
        # Le treasurer publie un bilan — on peut estimer le ROI social
        log("INFO", "Bilan financier reçu — calcul ROI social possible")

    elif channel == "social:scheduled":
        log("INFO", f"Contenu planifié: {payload.get('persona', '?')} — {payload.get('hook', '?')[:40]}")

    elif channel == "social:monetization":
        revenue = payload.get("revenue", 0)
        log("INFO", f"Monétisation: ${revenue}")
        # Notifier le treasurer
        publish("finance:report", {
            "agent": "adam-social",
            "type": "social_revenue",
            "revenue": revenue,
            "source": payload.get("persona", "unknown"),
        })

    else:
        log("WARN", f"Canal non géré: {channel}")

    return True

# ─── CLI ───
def main():
    parser = argparse.ArgumentParser(description="ADAM Social — Influence virtuelle & monétisation")
    parser.add_argument("--plan", action="store_true", help="Planifie le contenu de la semaine")
    parser.add_argument("--report", action="store_true", help="Bilan des personas et revenus estimés")
    parser.add_argument("--event", nargs=2, metavar=("CHANNEL", "PAYLOAD"),
                        help="Handler event bus: --event <channel> '<json>'")
    args = parser.parse_args()

    if args.plan:
        log("INFO", "=== Planification contenu social ===")
        calendar = plan_content(days=7)
        log("INFO", f"=== {len(calendar)} posts planifiés pour 7 jours ===")

    elif args.report:
        log("INFO", "=== Bilan Social ===")
        print("=" * 60)
        print("📱 ADAM-SOCIAL — Bilan Influence Virtuelle")
        print("=" * 60)
        for p in PERSONAS:
            eng = estimate_engagement(p["name"], "post")
            followers = max(p["followers_estimate"], 1000)  # minimum
            rev, breakdown = estimate_revenue(p, followers, eng)
            print(f"\n  @{p['name']} ({p['platform']}) — {p['niche']}")
            print(f"    Followers: {followers:,} | Engagement: {eng*100:.2f}%")
            print(f"    Revenu/mois: ${rev:.2f}")
            for stream, amount in breakdown.items():
                print(f"      └ {stream}: ${amount:.2f}")
        print("=" * 60)

    elif args.event:
        channel, payload = args.event
        handle_event(channel, payload)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
