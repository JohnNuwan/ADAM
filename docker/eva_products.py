#!/usr/bin/env python3
from flask import Flask
app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EVA — Produits & Services IA</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050510;color:#e0e8f0;font-family:'Inter',system-ui,sans-serif;overflow-x:hidden}

.hero{min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:40px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;top:0;left:0;right:0;bottom:0;background:radial-gradient(ellipse at center,rgba(0,170,255,0.08) 0%,transparent 70%);pointer-events:none}
.hero h1{font-size:64px;font-weight:900;background:linear-gradient(135deg,#00aaff,#00ff88,#ff8844);-webkit-background-clip:text;-webkit-text-fill-color:transparent;letter-spacing:-2px;margin-bottom:16px}
.hero p{font-size:20px;color:#6688aa;max-width:600px;line-height:1.6;margin-bottom:32px}
.hero .stats{display:flex;gap:40px;margin-top:20px}
.hero .stat{text-align:center}
.hero .stat .num{font-size:36px;font-weight:800;color:#00aaff}
.hero .stat .label{font-size:12px;color:#5577aa;text-transform:uppercase;letter-spacing:1px;margin-top:4px}

.products{padding:80px 40px;max-width:1200px;margin:0 auto}
.products h2{font-size:32px;font-weight:700;text-align:center;margin-bottom:12px}
.products .subtitle{font-size:14px;color:#5577aa;text-align:center;margin-bottom:48px}
.product-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px}

.product-card{background:rgba(10,15,25,0.6);border:1px solid rgba(255,255,255,0.06);border-radius:20px;padding:28px;transition:all 0.3s cubic-bezier(0.4,0,0.2,1);position:relative;overflow:hidden}
.product-card:hover{transform:translateY(-4px);border-color:rgba(0,170,255,0.2);box-shadow:0 20px 60px rgba(0,0,0,0.5)}
.product-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;background:linear-gradient(90deg,transparent,#00aaff,transparent);opacity:0;transition:opacity 0.3s}
.product-card:hover::before{opacity:1}
.product-card .category{font-size:10px;font-weight:600;color:#00aaff;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px}
.product-card h3{font-size:20px;font-weight:700;margin-bottom:8px;color:#e0e8f0}
.product-card .desc{font-size:13px;color:#88aacc;line-height:1.5;margin-bottom:16px}
.product-card .price{font-size:28px;font-weight:800;color:#00ff88;margin-bottom:16px}
.product-card .features{list-style:none;margin-bottom:20px}
.product-card .features li{font-size:12px;color:#88aacc;padding:4px 0;padding-left:24px;position:relative}
.product-card .features li::before{content:'✓';position:absolute;left:0;color:#00ff88;font-weight:700}
.product-card .target{font-size:11px;color:#5577aa;padding-top:12px;border-top:1px solid rgba(255,255,255,0.04)}
.product-card .target span{color:#88aacc}
.product-card .cta{display:inline-block;margin-top:16px;padding:10px 24px;background:linear-gradient(135deg,#0088cc,#00aaff);border:none;border-radius:10px;color:#fff;font-size:13px;font-weight:600;cursor:pointer;text-decoration:none;box-shadow:0 4px 16px rgba(0,170,255,0.2);transition:all 0.2s}
.product-card .cta:hover{transform:translateY(-1px);box-shadow:0 6px 24px rgba(0,170,255,0.3)}

.footer{padding:40px;text-align:center;color:#446688;font-size:12px;border-top:1px solid rgba(255,255,255,0.04);margin-top:40px}
.footer a{color:#00aaff;text-decoration:none}

@media(max-width:768px){.hero h1{font-size:42px}.hero .stats{flex-direction:column;gap:20px}}
</style>
</head>
<body>

<div class="hero">
  <h1>EVA</h1>
  <p>16 agents IA autonomes propulsés par Qwen2.5-32B. 1127 skills. 120+ outils. 100% local. Voici ce que EVA a créé et peut vendre.</p>
  <div class="stats">
    <div class="stat"><div class="num">19</div><div class="label">Agents IA</div></div>
    <div class="stat"><div class="num">1127</div><div class="label">Skills</div></div>
    <div class="stat"><div class="num">120+</div><div class="label">Outils créés</div></div>
    <div class="stat"><div class="num">4000+</div><div class="label">Leçons apprises</div></div>
  </div>
</div>

<div class="products">
  <h2>Produits & Services</h2>
  <p class="subtitle">Générés et développés par les agents ADAM autonomes</p>
  <div class="product-grid">

    <div class="product-card">
      <div class="category">Trading</div>
      <h3>EVA Smart Finance</h3>
      <p class="desc">Analyse et optimisez votre portefeuille d'investissement avec des recommandations en temps réel.</p>
      <div class="price">99€/mois</div>
      <ul class="features"><li>Analyse financière avancée</li><li>Recommandations d'investissement personnalisées</li><li>Suivi en temps réel des performances</li></ul>
      <div class="target">Cible: <span>Investisseurs privés et professionnels</span></div>
      <a href="#" class="cta">Demander une démo</a>
    </div>

    <div class="product-card">
      <div class="category">Sécurité</div>
      <h3>EVA Cyber Sentinel</h3>
      <p class="desc">Protection contre les cybermenaces avec une détection proactive et une réponse automatisée.</p>
      <div class="price">199€/mois</div>
      <ul class="features"><li>Détection prédictive des menaces</li><li>Réponse automatique à la menace</li><li>Rapports d'activité sécuritaire en temps réel</li></ul>
      <div class="target">Cible: <span>Entreprises de toutes tailles</span></div>
      <a href="#" class="cta">Demander une démo</a>
    </div>

    <div class="product-card">
      <div class="category">Contenu</div>
      <h3>EVA Content Forge</h3>
      <p class="desc">Créez du contenu engageant pour vos campagnes marketing grâce à notre IA de création.</p>
      <div class="price">49€/mois</div>
      <ul class="features"><li>Génération de contenu textuel et visuel</li><li>Personnalisation pour différents publics cibles</li><li>Optimisation SEO intégrée</li></ul>
      <div class="target">Cible: <span>Marketing managers et agences de communication</span></div>
      <a href="#" class="cta">Demander une démo</a>
    </div>

    <div class="product-card">
      <div class="category">Service</div>
      <h3>EVA Workforce Optimizer</h3>
      <p class="desc">Optimisez l'efficacité de votre main-d'œuvre grâce à des analyses et des recommandations précises.</p>
      <div class="price">149€/mois</div>
      <ul class="features"><li>Analyse de performance des employés</li><li>Recommandations pour l'amélioration des compétences</li><li>Prédiction de besoin en ressources humaines</li></ul>
      <div class="target">Cible: <span>RH et gestionnaires de projet</span></div>
      <a href="#" class="cta">Demander une démo</a>
    </div>

    <div class="product-card">
      <div class="category">Formation</div>
      <h3>EVA EduPro</h3>
      <p class="desc">Formation personnalisée en ligne avec des modules adaptatifs pour une efficacité maximale.</p>
      <div class="price">29€/mois</div>
      <ul class="features"><li>Modules de formation adaptatifs</li><li>Évaluation continue des compétences acquises</li><li>Certifications numériques</li></ul>
      <div class="target">Cible: <span>Apprenants individuels et entreprises</span></div>
      <a href="#" class="cta">Demander une démo</a>
    </div>

    <div class="product-card">
      <div class="category">SaaS</div>
      <h3>EVA MarketPulse</h3>
      <p class="desc">Analyse de marché en temps réel pour prendre des décisions commerciales éclairées.</p>
      <div class="price">79€/mois</div>
      <ul class="features"><li>Analyse de tendances de marché</li><li>Benchmarking concurrentiel</li><li>Prévisions de demande</li></ul>
      <div class="target">Cible: <span>Directeurs de la stratégie et analystes de marché</span></div>
      <a href="#" class="cta">Demander une démo</a>
    </div>

  </div>
</div>

<div class="footer">
  <p>EVA — Evolving Virtual Assistant · 100% local (Qwen2.5-32B-AWQ sur 2× RTX 3090)</p>
  <p>Créé par <a href="https://github.com/JohnNuwan/EVA_CORE">JohnNuwan/EVA_CORE</a> · Cycle 86+ · AGI Niveau 5/12</p>
</div>

</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8093)
