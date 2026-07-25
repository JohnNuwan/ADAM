#!/usr/bin/env python3
"""EVA Monitor — Page de monitoring des objectifs, P&L, et activité agents"""
from flask import Flask, jsonify, request
import json, os, urllib.request, time, threading
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
BUS_URL = "http://go-bus:8086"
VLLM_URL = os.environ.get("VLLM_URL", "http://192.168.1.5:8000")
DIRECTIVE_FILE = Path("/home/aza/eva-adam-v2/EVA_DIRECTIVE.md")
ADAM_DIR = Path("/data/agents")

# Cache
stats_cache = {"events": 0, "topics": {}, "ts": 0}
pnl_cache = {"daily": [], "weekly": [], "total": 0}
lock = threading.Lock()

def poll_stats():
    while True:
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/stats")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                with lock:
                    stats_cache.clear()
                    stats_cache.update(data)
                    stats_cache["ts"] = time.time()
        except:
            pass
        time.sleep(10)

threading.Thread(target=poll_stats, daemon=True).start()

@app.route("/api/directive")
def api_directive():
    try:
        if DIRECTIVE_FILE.exists():
            return jsonify({"directive": DIRECTIVE_FILE.read_text()[:5000]})
    except:
        pass
    return jsonify({"directive": ""})

@app.route("/api/stats")
def api_stats():
    with lock:
        return jsonify(stats_cache)

@app.route("/api/agents")
def api_agents():
    """Get agent status from Go Bus"""
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=30&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            pkts = data if isinstance(data, list) else data.get("events", [])
            pkts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            agents = {}
            for p in pkts:
                src = p.get("source", "")
                if src and src not in agents:
                    payload = p.get("payload", {})
                    if not isinstance(payload, dict): payload = {}
                    agents[src] = {
                        "thought": payload.get("thought", payload.get("output", ""))[:120],
                        "mission": payload.get("mission", "")[:80],
                        "status": payload.get("status", ""),
                        "tools": payload.get("tools_created", []),
                        "timestamp": p.get("timestamp", "")
                    }
            return jsonify({"agents": agents})
    except:
        return jsonify({"agents": {}})

@app.route("/api/missions")
def api_missions():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:mission")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            missions = data if isinstance(data, list) else data.get("events", [])
            return jsonify({"missions": missions})
    except:
        return jsonify({"missions": []})

@app.route("/api/tools")
def api_tools():
    """Get tools created by agents"""
    try:
        tools_data = {}
        if ADAM_DIR.exists():
            for d in sorted(ADAM_DIR.iterdir()):
                if d.is_dir():
                    name = "adam-" + d.name
                    scripts = [f.name for f in sorted(d.glob("*.sh")) + sorted(d.glob("*.py"))]
                    tools = []
                    tdir = d / "tools"
                    if tdir.exists():
                        tools = [f.name for f in sorted(tdir.iterdir()) if f.is_file()]
                    if scripts or tools:
                        tools_data[name] = {"scripts": scripts[:10], "tools": tools[:10]}
        return jsonify({"tools": tools_data, "total": sum(len(v.get("tools",[])) for v in tools_data.values())})
    except:
        return jsonify({"tools": {}, "total": 0})

@app.route("/api/memory")
def api_memory():
    """Get memory stats per agent"""
    try:
        memory_stats = {}
        if ADAM_DIR.exists():
            for d in sorted(ADAM_DIR.iterdir()):
                if d.is_dir():
                    name = "adam-" + d.name
                    mdir = d / "memory"
                    missions_count = 0
                    lessons_count = 0
                    if mdir.exists():
                        mf = mdir / "missions.json"
                        lf = mdir / "lessons.json"
                        if mf.exists():
                            try:
                                data = json.loads(mf.read_text())
                                missions_count = len(data.get("missions", []))
                            except: pass
                        if lf.exists():
                            try:
                                data = json.loads(lf.read_text())
                                lessons_count = len(data.get("lessons", []))
                            except: pass
                    if missions_count or lessons_count:
                        memory_stats[name] = {"missions": missions_count, "lessons": lessons_count}
        return jsonify({"memory": memory_stats})
    except:
        return jsonify({"memory": {}})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EVA Monitor — Objectifs & Activité</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a14;color:#e0e8f0;font-family:'SF Pro Display','Segoe UI',system-ui,sans-serif}
.container{max-width:1400px;margin:0 auto;padding:20px}

h1{font-size:22px;font-weight:700;margin-bottom:5px;background:linear-gradient(90deg,#00aaff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.subtitle{font-size:12px;color:#5577aa;margin-bottom:20px}

.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:16px;margin-bottom:20px}

.card{background:rgba(10,15,25,0.8);border:1px solid rgba(68,102,136,0.15);border-radius:12px;padding:16px;overflow:hidden}
.card h2{font-size:11px;color:#5577aa;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.card h2 .dot{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}

/* Objectifs */
.objective{padding:10px 0;border-bottom:1px solid rgba(68,102,136,0.08)}
.objective:last-child{border:none}
.objective .title{font-size:13px;font-weight:600;margin-bottom:4px}
.objective .desc{font-size:11px;color:#88aacc;line-height:1.5}
.objective .priority{font-size:9px;padding:2px 8px;border-radius:8px;display:inline-block;margin-top:4px;font-weight:600}
.priority.critical{background:#ff446622;color:#ff4466}
.priority.high{background:#ffaa4422;color:#ffaa44}
.priority.medium{background:#00aaff22;color:#00aaff}

/* Agent status */
.agent-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(68,102,136,0.06)}
.agent-row:last-child{border:none}
.agent-row .name{font-size:12px;font-weight:600;color:#00ff88;min-width:100px}
.agent-row .mission{font-size:10px;color:#88aacc;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.agent-row .time{font-size:9px;color:#446688;min-width:55px;text-align:right}
.agent-row .status{width:8px;height:8px;border-radius:50%;min-width:8px}
.status.done{background:#00ff88}
.status.failed{background:#ff4466}
.status.timeout{background:#ffaa44}
.status.running{background:#00aaff;animation:pulse 1s infinite}

/* Stats */
.stat-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stat{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;text-align:center}
.stat .val{font-size:20px;font-weight:700;color:#00aaff}
.stat .label{font-size:9px;color:#5577aa;text-transform:uppercase;margin-top:2px}

/* Tools */
.tool-item{font-size:10px;font-family:monospace;color:#ffaa00;padding:3px 0;border-bottom:1px solid rgba(68,102,136,0.04)}
.tool-item .agent{color:#00ff88;margin-right:8px}

/* Memory */
.mem-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(68,102,136,0.06)}
.mem-row .name{font-size:11px;color:#00ff88;font-weight:600}
.mem-row .count{font-size:11px;color:#88aacc}
.mem-row .bar{height:4px;background:rgba(68,102,136,0.2);border-radius:2px;margin-top:4px;overflow:hidden}
.mem-row .bar-fill{height:100%;background:linear-gradient(90deg,#00aaff,#00ff88);border-radius:2px}

/* Budget */
.budget-table{width:100%;font-size:11px}
.budget-table th{text-align:left;color:#5577aa;padding:6px;border-bottom:1px solid rgba(68,102,136,0.1);font-size:10px;text-transform:uppercase}
.budget-table td{padding:6px;border-bottom:1px solid rgba(68,102,136,0.05)}
.budget-table .income{color:#00ff88;font-weight:600}
.budget-table .expense{color:#ff4466}
.budget-table .total{font-weight:700;font-size:13px}

/* AGI levels */
.agi-level{display:flex;align-items:center;gap:8px;padding:6px 0}
.agi-level .num{width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}
.agi-level .num.done{background:#00ff8833;color:#00ff88}
.agi-level .num.current{background:#00aaff33;color:#00aaff;border:2px solid #00aaff}
.agi-level .num.future{background:rgba(68,102,136,0.2);color:#5577aa}
.agi-level .text{font-size:11px;color:#88aacc}
.agi-level .text.done{color:#00ff88}
.agi-level .text.current{color:#00aaff;font-weight:600}
</style>
</head>
<body>
<div class="container">
  <h1>EVA Monitor</h1>
  <div class="subtitle">Monitoring des objectifs, activité agents, et progression AGI</div>

  <!-- Stats globales -->
  <div class="grid">
    <div class="card">
      <h2><span class="dot"></span>Statut Système</h2>
      <div class="stat-grid" id="stats-grid">
        <div class="stat"><div class="val" id="stat-events">-</div><div class="label">Events</div></div>
        <div class="stat"><div class="val" id="stat-agents">-</div><div class="label">Agents</div></div>
        <div class="stat"><div class="val" id="stat-tools">-</div><div class="label">Outils</div></div>
      </div>
    </div>

    <div class="card">
      <h2><span class="dot"></span>Agents Actifs</h2>
      <div id="agents-list"></div>
    </div>

    <div class="card" style="min-height:300px">
      <h2><span class="dot"></span>Missions en cours (Live)</h2>
      <div id="missions-list"></div>
    </div>
  </div>

  <!-- Objectifs -->
  <div class="grid">
    <div class="card">
      <h2><span class="dot"></span>Objectifs EVA</h2>
      <div id="objectives-list"></div>
    </div>

    <div class="card">
      <h2><span class="dot"></span>Budget Mensuel</h2>
      <table class="budget-table">
        <tr><th colspan="3" style="color:#ff4466">DETTE MATÉRIELLE</th></tr>
        <tr><td>Processeur</td><td colspan="2" class="expense">-200€</td></tr>
        <tr><td>2× RTX 3090 (800€/u)</td><td colspan="2" class="expense">-1600€</td></tr>
        <tr><td>Carte mère</td><td colspan="2" class="expense">-1000€</td></tr>
        <tr><td>RAM</td><td colspan="2" class="expense">-400€</td></tr>
        <tr><td>Alimentation</td><td colspan="2" class="expense">-200€</td></tr>
        <tr><td>Boîtier</td><td colspan="2" class="expense">-200€</td></tr>
        <tr><td>Disques durs</td><td colspan="2" class="expense">-300€</td></tr>
        <tr><td>Programmation EVA</td><td colspan="2" class="expense">-500€</td></tr>
        <tr class="total"><td>Dette totale</td><td colspan="2" class="expense">-4400€</td></tr>
        <tr><td colspan="3" style="height:8px"></td></tr>
        <tr><th>Coûts mensuels</th><th>Actuel</th><th>Objectif</th></tr>
        <tr><td>Électricité</td><td class="expense">-150€</td><td class="expense">-120€</td></tr>
        <tr><td>Infrastructure</td><td class="expense">-100€</td><td class="expense">-80€</td></tr>
        <tr class="total"><td>Total/mois</td><td class="expense">-250€</td><td class="expense">-200€</td></tr>
        <tr><td colspan="3" style="height:8px"></td></tr>
        <tr><th>Revenus & Remboursement</th><th>Actuel</th><th>Objectif</th></tr>
        <tr><td>Revenus bruts/mois</td><td>0€</td><td class="income">+10000€</td></tr>
        <tr><td>Impôts (~25%)</td><td>0€</td><td class="expense">-2500€</td></tr>
        <tr><td>Revenus nets/mois</td><td>0€</td><td class="income">+7500€</td></tr>
        <tr><td>Coûts mensuels</td><td class="expense">-250€</td><td class="expense">-200€</td></tr>
        <tr><td>Remboursement dette/mois</td><td>0€</td><td class="expense">-550€</td></tr>
        <tr><td>Composants/mois</td><td>0€</td><td class="expense">-500€</td></tr>
        <tr class="total"><td>Bénéfice net/mois</td><td class="expense">-250€</td><td class="income">+6250€</td></tr>
        <tr><td colspan="3" style="height:8px"></td></tr>
        <tr class="total"><td>Dette restante</td><td colspan="2" style="color:#ffaa44">4400€ → 0€ en 2 mois</td></tr>
        <tr><td colspan="3" style="height:8px"></td></tr>
        <tr><th colspan="3" style="color:#00ff88">PROGRESSION REVENUS</th></tr>
        <tr><td colspan="3" id="revenue-progress" style="padding:10px">
          <div style="background:rgba(68,102,136,0.2);border-radius:8px;height:20px;overflow:hidden">
            <div id="revenue-bar" style="height:100%;width:0%;background:linear-gradient(90deg,#ff4466,#ffaa44,#00ff88);border-radius:8px;transition:width 0.5s"></div>
          </div>
          <div style="font-size:10px;color:#5577aa;margin-top:4px"><span id="revenue-current">0€</span> / 10000€ objectif</div>
        </td></tr>
      </table>
    </div>

    <div class="card">
      <h2><span class="dot"></span>Progression AGI</h2>
      <div id="agi-levels"></div>
    </div>
  </div>

  <!-- Outils + Mémoire -->
  <div class="grid">
    <div class="card">
      <h2><span class="dot"></span>Outils créés par les Agents</h2>
      <div id="tools-list"></div>
    </div>

    <div class="card">
      <h2><span class="dot"></span>Mémoire par Agent</h2>
      <div id="memory-list"></div>
    </div>
  </div>
</div>

<script>
function fetchAll() {
  fetchStats();
  fetchAgents();
  fetchMissions();
  fetchTools();
  fetchMemory();
}

function fetchStats() {
  fetch('/api/stats').then(r=>r.json()).then(d=>{
    document.getElementById('stat-events').textContent = d.history_events || 0;
    document.getElementById('stat-agents').textContent = Object.keys(d).filter(k=>k.startsWith('topic:adam:packet')).length;
  });
  fetch('/api/tools').then(r=>r.json()).then(d=>{
    document.getElementById('stat-tools').textContent = d.total || 0;
  });
  // Update revenue progress (simulated for now)
  var revenue = 0; // TODO: connect to real revenue data
  var pct = Math.min(100, (revenue / 10000) * 100);
  var bar = document.getElementById('revenue-bar');
  if (bar) bar.style.width = pct + '%';
  var cur = document.getElementById('revenue-current');
  if (cur) cur.textContent = revenue + '€';
}

function fetchAgents() {
  fetch('/api/agents').then(r=>r.json()).then(d=>{
    var el = document.getElementById('agents-list');
    var agents = d.agents || {};
    var keys = Object.keys(agents).sort();
    var html = '';
    for (var i=0; i<keys.length; i++) {
      var a = agents[keys[i]];
      var t = (a.timestamp||'').slice(11,19) || '--:--:--';
      var st = a.status || 'done';
      var mission = a.mission || a.thought || '';
      html += '<div class="agent-row"><div class="status '+st+'"></div><div class="name">'+keys[i]+'</div><div class="mission">'+mission.substring(0,60)+'</div><div class="time">'+t+'</div></div>';
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px">Aucun agent actif</div>';
    el.innerHTML = html;
  });
}

function fetchMissions() {
  fetch('/api/missions').then(r=>r.json()).then(d=>{
    var el = document.getElementById('missions-list');
    var missions = d.missions || [];
    var html = '';
    for (var i=0; i<Math.min(missions.length,10); i++) {
      var m = missions[i];
      var p = m.payload || {};
      var st = p.status || 'pending';
      var agent = (p.agent||m.source||'').replace('adam-','');
      var mission = (p.mission||p.objective||m.topic||'').substring(0,60);
      var t = (m.timestamp||'').slice(11,19) || '--:--:--';
      var stColor = st==='done'?'#00ff88':(st==='failed'?'#ff4466':(st==='running'?'#00aaff':'#ffaa44'));
      var tools = p.tools_created || [];
      var thought = p.thought || '';
      html += '<div style="padding:8px;border-bottom:1px solid rgba(68,102,136,0.08)">';
      html += '<div style="display:flex;align-items:center;gap:8px">';
      html += '<div class="status '+st+'" style="width:8px;height:8px;border-radius:50%;min-width:8px;background:'+stColor+'"></div>';
      html += '<div style="font-size:11px;font-weight:600;color:#00ff88;min-width:80px">'+agent+'</div>';
      html += '<div style="font-size:10px;color:#88aacc;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+mission+'</div>';
      html += '<div style="font-size:9px;color:#446688">'+t+'</div>';
      html += '</div>';
      if (thought) {
        html += '<div style="font-size:9px;color:#6688aa;margin-top:3px;margin-left:16px;font-style:italic">'+thought.substring(0,80)+'</div>';
      }
      if (tools && tools.length) {
        html += '<div style="font-size:9px;color:#ffaa00;margin-top:2px;margin-left:16px">🔧 '+tools.join(', ').substring(0,60)+'</div>';
      }
      // Progress bar
      var pct = st==='done'?100:(st==='running'?50:(st==='failed'?100:10));
      html += '<div style="height:2px;background:rgba(68,102,136,0.15);border-radius:1px;margin-top:4px;margin-left:16px;overflow:hidden">';
      html += '<div style="height:100%;width:'+pct+'%;background:'+stColor+';border-radius:1px;transition:width 0.3s"></div>';
      html += '</div>';
      html += '</div>';
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px">Aucune mission</div>';
    el.innerHTML = html;
  });
}

function fetchTools() {
  fetch('/api/tools').then(r=>r.json()).then(d=>{
    var el = document.getElementById('tools-list');
    var tools = d.tools || {};
    var html = '';
    for (var agent in tools) {
      var t = tools[agent].tools || [];
      for (var i=0; i<t.length; i++) {
        if (t[i] !== 'registry.json') {
          html += '<div class="tool-item"><span class="agent">'+agent.replace('adam-','')+'</span>'+t[i]+'</div>';
        }
      }
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px">Aucun outil</div>';
    el.innerHTML = html;
  });
}

function fetchMemory() {
  fetch('/api/memory').then(r=>r.json()).then(d=>{
    var el = document.getElementById('memory-list');
    var mem = d.memory || {};
    var keys = Object.keys(mem).sort();
    var maxMissions = 1;
    for (var k in mem) { if (mem[k].missions > maxMissions) maxMissions = mem[k].missions; }
    var html = '';
    for (var i=0; i<keys.length; i++) {
      var m = mem[keys[i]];
      var pct = Math.round((m.missions / maxMissions) * 100);
      html += '<div class="mem-row"><div><div class="name">'+keys[i].replace('adam-','')+'</div><div class="bar"><div class="bar-fill" style="width:'+pct+'%"></div></div></div><div class="count">'+m.missions+' missions / '+m.lessons+' lecons</div></div>';
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px">Aucune memoire</div>';
    el.innerHTML = html;
  });
}

// Objectives with live progress
function fetchObjectives() {
  // Calculate progress from real data
  Promise.all([
    fetch('/api/stats').then(r=>r.json()).catch(()=>({})),
    fetch('/api/tools').then(r=>r.json()).catch(()=>({tools:{},total:0})),
    fetch('/api/memory').then(r=>r.json()).catch(()=>({memory:{}})),
    fetch('/api/agents').then(r=>r.json()).catch(()=>({agents:{}})),
  ]).then(function(results) {
    var stats = results[0] || {};
    var tools = results[1] || {total:0};
    var mem = results[2] || {memory:{}};
    var agents = results[3] || {agents:{}};
    
    var totalEvents = stats.history_events || 0;
    var totalTools = tools.total || 0;
    var totalMissions = 0;
    var totalLessons = 0;
    for (var k in mem.memory) {
      totalMissions += mem.memory[k].missions || 0;
      totalLessons += mem.memory[k].lessons || 0;
    }
    var activeAgents = Object.keys(agents.agents || {}).length;
    
    // Calculate progress for each objective
    var objectives = [
      {
        title: '1. Autofinancement',
        desc: 'Trading Freedom24, monétisation Maeve.tech, opportunités revenu IA',
        priority: 'critical',
        target: '10,000€/mois',
        current: '0€/mois',
        pct: 0,
        subtasks: [
          {label: 'Treasurer actif', done: agents.agents && agents.agents['treasurer'] ? true : false},
          {label: 'Social actif (Maeve.tech)', done: agents.agents && agents.agents['social'] ? true : false},
          {label: 'Outil de trading créé', done: false},
          {label: 'Stratégie validée', done: false},
          {label: 'Premier revenu', done: false},
        ]
      },
      {
        title: '2. Auto-Évolution',
        desc: 'Créer skills, améliorer code, optimiser performances',
        priority: 'high',
        target: '1 amélioration/cycle',
        current: totalTools + ' outils créés',
        pct: Math.min(100, Math.round(totalTools / 50 * 100)),
        subtasks: [
          {label: 'Skillsmith actif', done: agents.agents && agents.agents['skillsmith'] ? true : false},
          {label: 'Critic actif', done: agents.agents && agents.agents['critic'] ? true : false},
          {label: 'Outils créés (' + totalTools + '/50)', done: totalTools >= 50, partial: totalTools},
          {label: 'Leçons apprises (' + totalLessons + ')', done: totalLessons > 50, partial: totalLessons},
          {label: 'Praetor optimisation', done: agents.agents && agents.agents['praetor'] ? true : false},
        ]
      },
      {
        title: '3. AGI — Auto-Amélioration',
        desc: 'Recherche auto-amélioration, raisonnement général',
        priority: 'high',
        target: 'Niveau 6 (AGI)',
        current: 'Niveau 1/6',
        pct: 17,
        subtasks: [
          {label: 'Niveau 1: Missions assignées', done: true},
          {label: 'Niveau 2: Missions autonomes', done: true},
          {label: 'Niveau 3: Agents créent agents', done: false},
          {label: 'Niveau 4: Auto-modification code', done: false},
          {label: 'Niveau 5: Auto-gestion infra', done: false},
          {label: 'Niveau 6: AGI', done: false},
        ]
      },
      {
        title: '4. Optimisation des Coûts',
        desc: 'Monitorer GPU/CPU/RAM, réduire coût de 20%',
        priority: 'medium',
        target: '-20% en 3 mois',
        current: '-250€/mois',
        pct: 10,
        subtasks: [
          {label: 'Doctor monitoring actif', done: agents.agents && agents.agents['doctor'] ? true : false},
          {label: 'Mesure consommation GPU', done: false},
          {label: 'Optimisation batch inference', done: false},
          {label: 'Objectif -20% atteint', done: false},
        ]
      },
      {
        title: '5. Sécurité & Robustesse',
        desc: 'Hardening continu, veille CVE, tests intrusion',
        priority: 'medium',
        target: '0 faille critique',
        current: 'Active',
        pct: Math.min(100, Math.round((totalMissions > 0 ? 30 : 0) + (totalLessons > 10 ? 20 : 0))),
        subtasks: [
          {label: 'Sentinel veille CVE', done: agents.agents && agents.agents['sentinel'] ? true : false},
          {label: 'Blue-Team hardening', done: agents.agents && agents.agents['blue-team'] ? true : false},
          {label: 'Red-Team tests intrusion', done: agents.agents && agents.agents['red-team'] ? true : false},
          {label: 'Outil de scan créé', done: totalTools > 5},
          {label: 'Zéro faille critique', done: false},
        ]
      },
    ];
    
    var html = '';
    for (var i=0; i<objectives.length; i++) {
      var o = objectives[i];
      var pctColor = o.pct >= 80 ? '#00ff88' : (o.pct >= 40 ? '#ffaa44' : '#ff4466');
      
      html += '<div class="objective">';
      html += '<div style="display:flex;justify-content:space-between;align-items:center">';
      html += '<div class="title">'+o.title+'</div>';
      html += '<div class="priority '+o.priority+'">'+o.priority.toUpperCase()+'</div>';
      html += '</div>';
      html += '<div class="desc">'+o.desc+'</div>';
      
      // Progress bar
      html += '<div style="margin-top:8px">';
      html += '<div style="display:flex;justify-content:space-between;font-size:9px;color:#5577aa;margin-bottom:3px">';
      html += '<span>'+o.current+'</span><span>'+o.target+'</span>';
      html += '</div>';
      html += '<div style="background:rgba(68,102,136,0.2);border-radius:4px;height:6px;overflow:hidden">';
      html += '<div style="height:100%;width:'+o.pct+'%;background:linear-gradient(90deg,'+pctColor+','+pctColor+'88);border-radius:4px;transition:width 0.5s"></div>';
      html += '</div>';
      html += '<div style="font-size:9px;color:'+pctColor+';margin-top:2px;font-weight:600">'+o.pct+'%</div>';
      html += '</div>';
      
      // Subtasks
      html += '<div style="margin-top:8px;font-size:10px">';
      for (var j=0; j<o.subtasks.length; j++) {
        var s = o.subtasks[j];
        var icon = s.done ? '✅' : '⬜';
        var color = s.done ? '#00ff88' : '#5577aa';
        html += '<div style="padding:2px 0;color:'+color+'">'+icon+' '+s.label+'</div>';
      }
      html += '</div>';
      html += '</div>';
    }
    document.getElementById('objectives-list').innerHTML = html;
  });
}

// AGI levels
var agiLevels = [
  {num:1, text:'Agents exécutent missions assignées', done:true},
  {num:2, text:'Agents choisissent leurs propres missions', done:false, current:true},
  {num:3, text:'Agents créent de nouveaux agents spécialisés', done:false},
  {num:4, text:'Agents modifient leur propre code source', done:false},
  {num:5, text:'Agents gèrent leur propre infrastructure', done:false},
  {num:6, text:'AGI — raisonnement général, créativité', done:false},
];
var agiHtml = '';
for (var i=0; i<agiLevels.length; i++) {
  var cls = agiLevels[i].done ? 'done' : (agiLevels[i].current ? 'current' : 'future');
  agiHtml += '<div class="agi-level"><div class="num '+cls+'">'+agiLevels[i].num+'</div><div class="text '+cls+'">'+agiLevels[i].text+'</div></div>';
}
document.getElementById('agi-levels').innerHTML = agiHtml;

// Start
fetchAll();
fetchObjectives();
setInterval(fetchAll, 5000);
setInterval(fetchObjectives, 10000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8091)
