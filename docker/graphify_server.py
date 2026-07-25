#!/usr/bin/env python3
"""Graphify 3D V6 - Holographic Cyber-Grid Network Topology"""
from flask import Flask, jsonify, request
import psycopg2, json, os, urllib.request, time, threading, random
from datetime import datetime, timezone

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:adam_secret_2026@postgres:5432/adam?sslmode=disable")
BUS_URL = os.environ.get("BUS_URL", "http://go-bus:8086")

nodes_cache = {"nodes": [], "edges": [], "ts": 0}
lock = threading.Lock()

def refresh_graph():
    while True:
        try:
            pg = psycopg2.connect(PG_DSN)
            cur = pg.cursor()
            nodes = []
            cur.execute("SELECT id, label, name, properties FROM knowledge_nodes LIMIT 500")
            for row in cur:
                props = row[3] or {}
                nodes.append({"id": str(row[0]), "label": row[1], "name": row[2],
                              "properties": props if isinstance(props, dict) else {}})
            edges = []
            cur.execute("SELECT source_id, target_id, relation FROM knowledge_edges LIMIT 2000")
            for row in cur:
                edges.append({"source": str(row[0]), "target": str(row[1]), "relation": row[2]})
            cur.close(); pg.close()
            with lock:
                nodes_cache["nodes"] = nodes
                nodes_cache["edges"] = edges
                nodes_cache["ts"] = time.time()
        except Exception as e:
            print(f"[ERR] {e}", flush=True)
        time.sleep(10)

threading.Thread(target=refresh_graph, daemon=True).start()

@app.route("/api/graph")
def get_graph():
    with lock:
        return jsonify(nodes_cache)

@app.route("/api/packets")
def get_packets():
    try:
        # Fetch packets directly from PostgreSQL database to resolve empty query bug
        pg = psycopg2.connect(PG_DSN)
        cur = pg.cursor()
        cur.execute("""
            SELECT topic, source, payload, created_at
            FROM events
            ORDER BY created_at DESC
            LIMIT 15
        """)
        packets = []
        for row in cur:
            payload = row[2]
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            
            created_at = row[3]
            if isinstance(created_at, datetime):
                created_at = created_at.isoformat()
            elif created_at:
                created_at = str(created_at)

            packets.append({
                "topic": row[0],
                "source": row[1],
                "payload": payload if isinstance(payload, dict) else {},
                "timestamp": created_at
            })
        cur.close(); pg.close()
        return jsonify({"packets": packets})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

@app.route("/api/simulate", methods=["POST"])
def simulate_event():
    try:
        # Simulate active agent events on the event bus
        agents = ["red-team", "blue-team", "sentinel", "critic", "scribe", "skillsmith", "doctor", "treasurer", "osint"]
        topics = ["adam:packet", "adam:mission", "finance:alert", "ctf:solved"]
        status = ["done", "failed", "timeout"]

        agent = random.choice(agents)
        topic = random.choice(topics)
        stat = random.choice(status)

        payload = {
            "agent": agent,
            "status": stat,
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Format and send payload to Go-Bus broker
        d = json.dumps({
            "topic": topic,
            "source": agent,
            "payload": payload,
            "priority": 1,
        }).encode()

        req = urllib.request.Request(f"{BUS_URL}/api/publish", data=d, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
        return jsonify({"status": "ok", "simulated": payload})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM HUD - Topology Matrix</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#020205;color:#e2e5f5;font-family:'Outfit',sans-serif;overflow:hidden}
#app{width:100vw;height:100vh}

/* Top bar styling */
#topbar{
  position:fixed;
  top:0;
  left:0;
  right:0;
  height:50px;
  background:rgba(2,2,5,0.7);
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:0 24px;
  z-index:100;
  backdrop-filter:blur(16px);
  border-bottom:1px solid rgba(0,240,255,0.2);
  box-shadow:0 4px 24px rgba(0,0,0,0.6);
}
#topbar .logo{display:flex;align-items:center;gap:12px}
#topbar .logo .dot{
  width:9px;
  height:9px;
  border-radius:50%;
  background:#00f0ff;
  box-shadow:0 0 12px #00f0ff;
  animation:pulse 2s infinite;
}
#topbar .logo span{
  font-size:15px;
  font-weight:700;
  letter-spacing:1.5px;
  text-transform:uppercase;
  background:linear-gradient(90deg, #00f0ff, #d500f9);
  -webkit-background-clip:text;
  -webkit-text-fill-color:transparent;
}
#topbar .stats{display:flex;gap:15px;font-size:11px;color:#718bb2}
#topbar .stats div{background:rgba(255,255,255,0.02);padding:4px 8px;border-radius:6px;border:1px solid rgba(255,255,255,0.04)}
#topbar .stats .val{color:#00f0ff;font-weight:700;margin-left:3px}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.4;transform:scale(0.9)}}

/* Panels - Cyber HUD Glassmorphism */
.panel {
  background:rgba(6,8,20,0.85);
  border:1px solid rgba(0,240,255,0.2);
  backdrop-filter:blur(16px);
  border-radius:12px;
  box-shadow:0 8px 32px 0 rgba(0,0,0,0.7);
  z-index:50;
  position:fixed;
  transition:all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

#info{
  top:70px;
  left:20px;
  padding:20px;
  width:320px;
  opacity:0;
  transform:translateX(-25px);
  pointer-events:none;
}
#info.visible{opacity:1;transform:translateX(0);pointer-events:auto;}
#info h3{margin:0 0 4px;font-size:17px;font-weight:700;color:#fff;letter-spacing:0.5px}
#info .tag{
  display:inline-block;
  font-size:9px;
  padding:2px 8px;
  border-radius:4px;
  margin-bottom:12px;
  text-transform:uppercase;
  letter-spacing:1px;
  font-weight:700;
  border:1px solid currentColor;
}
#info .props{
  font-size:12px;
  line-height:1.7;
  color:#9ebcd9;
  max-height:220px;
  overflow-y:auto;
}
#info .props::-webkit-scrollbar{width:3px}
#info .props::-webkit-scrollbar-thumb{background:rgba(0,240,255,0.3);border-radius:2px}
#info .props div{
  display:flex;
  justify-content:space-between;
  padding:5px 0;
  border-bottom:1px solid rgba(255,255,255,0.03);
}
#info .props .k{color:#718bb2;font-weight:500;text-transform:capitalize}

#legend{
  bottom:20px;
  left:20px;
  padding:16px;
  width:260px;
}
#legend h4{font-size:10px;color:#00f0ff;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;font-weight:700}
#legend .item{display:flex;align-items:center;gap:10px;font-size:12px;padding:3px 0;color:#b2c6df}
#legend .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;box-shadow:0 0 8px currentColor}
#legend .count{color:#5678a0;font-size:10px;margin-left:auto;font-weight:700}

#packet-stream{
  bottom:20px;
  right:20px;
  padding:16px;
  width:380px;
  height:320px;
  display:flex;
  flex-direction:column;
}
#packet-stream h4{
  font-size:11px;
  color:#00ff88;
  margin-bottom:10px;
  text-transform:uppercase;
  letter-spacing:1px;
  display:flex;
  align-items:center;
  justify-content:space-between;
  font-weight:700;
}
#packet-stream h4 div{display:flex;align-items:center;gap:6px}
#packet-stream .live{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:pulse 1s infinite}
#packet-list{
  flex:1;
  overflow-y:auto;
  padding-right:5px;
}
#packet-list::-webkit-scrollbar{width:3px}
#packet-list::-webkit-scrollbar-thumb{background:rgba(0,255,136,0.3);border-radius:2px}

.pkt{
  color:#b2c6df;
  padding:5px 0;
  border-bottom:1px solid rgba(0,240,255,0.06);
  font-size:10.5px;
  font-family:'Consolas','SF Mono',monospace;
  display:flex;
  align-items:center;
  gap:8px;
}
.pkt .t{color:#5678a0}
.pkt .s{color:#00f0ff;font-weight:700;min-width:65px}
.pkt .top{color:#aabfdf;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pkt .st{
  font-size:8px;
  padding:1px 4px;
  border-radius:3px;
  font-weight:700;
  text-transform:uppercase;
  border:1px solid currentColor;
}

/* Simulation Button */
.btn-sim{
  background:rgba(0,240,255,0.1);
  border:1px solid #00f0ff;
  color:#00f0ff;
  padding:4px 10px;
  border-radius:4px;
  font-size:10px;
  font-family:'Outfit',sans-serif;
  cursor:pointer;
  font-weight:700;
  text-transform:uppercase;
  transition:all 0.2s;
}
.btn-sim:hover{
  background:#00f0ff;
  color:#020205;
  box-shadow:0 0 10px rgba(0,240,255,0.4);
}

.node-label{
  position:absolute;
  font-size:9.5px;
  font-weight:700;
  font-family:'Outfit',sans-serif;
  color:#fff;
  background:rgba(4,6,15,0.9);
  border:1px solid rgba(0,240,255,0.25);
  padding:2px 6px;
  border-radius:4px;
  pointer-events:none;
  white-space:nowrap;
  z-index:5;
  transform:translate(-50%,-130%);
  box-shadow:0 4px 12px rgba(0,0,0,0.6);
  letter-spacing:0.5px;
  text-transform:uppercase;
}

#hint{
  position:fixed;
  bottom:350px;
  right:20px;
  z-index:50;
  font-size:11px;
  color:#5678a0;
  line-height:1.8;
  text-align:right;
  background:rgba(2,2,5,0.5);
  padding:6px 12px;
  border-radius:6px;
  border:1px solid rgba(255,255,255,0.05);
}
</style>
</head>
<body>
<div id="app"></div>
<div id="topbar">
  <div class="logo"><div class="dot"></div><span>ADAM Topology Matrix</span></div>
  <div class="stats" id="stats-bar"></div>
</div>
<div id="info" class="panel">
  <h3 id="info-name">-</h3>
  <div class="tag" id="info-tag"></div>
  <div class="props" id="info-props"></div>
</div>
<div id="legend" class="panel">
  <h4>Topologie</h4>
  <div id="legend-items"></div>
</div>
<div id="packet-stream" class="panel">
  <h4>
    <div><span class="live"></span>Flux Réseau Temps Réel</div>
    <button class="btn-sim" onclick="simulateEvent()">Simuler Flux</button>
  </h4>
  <div id="packet-list"></div>
</div>
<div id="hint">Glisser: Orbiter | Molette: Zoom | Clic: Détails</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var scene, camera, renderer, controls;
var meshes = {};
var edgeLines = [];
var raycaster, pointer;
var selected = null;
var animTime = 0;
var clock = new THREE.Clock();

var activeParticles = [];
var activeFlashes = [];
var lastPacketTime = null;

// Symmetrical fixed locations for agents (radius = 9 on XZ plane)
var AGENT_PLANETS = {
  "praetor":      {index: 0,  color: 0xff3333, clr: "#ff3333", role: "Auto-correction"},
  "sentinel":     {index: 1,  color: 0x00f0ff, clr: "#00f0ff", role: "Veille Sécurité"},
  "critic":       {index: 2,  color: 0xffea00, clr: "#ffea00", role: "Revue de Code"},
  "scribe":       {index: 3,  color: 0x33aaff, clr: "#33aaff", role: "Documentation"},
  "skillsmith":   {index: 4,  color: 0x00e676, clr: "#00e676", role: "Gestion Skills"},
  "doctor":       {index: 5,  color: 0xb042ff, clr: "#b042ff", role: "Diagnostic/Soin"},
  "treasurer":    {index: 6,  color: 0xff9100, clr: "#ff9100", role: "Suivi Financier"},
  "social":       {index: 7,  color: 0xff4081, clr: "#ff4081", role: "Réseaux Sociaux"},
  "osint":        {index: 8,  color: 0x00bfa5, clr: "#00bfa5", role: "Collecte OSINT"},
  "researcher":   {index: 9,  color: 0x40c4ff, clr: "#40c4ff", role: "Scan Vulns"},
  "rag":          {index: 10, color: 0xaeea00, clr: "#aeea00", role: "Recherche RAG"},
  "viz":          {index: 11, color: 0x00e5ff, clr: "#00e5ff", role: "Dashboard 3D"},
  "ctf":          {index: 12, color: 0x7c4dff, clr: "#7c4dff", role: "Challenge CTF"},
  "blue-team":    {index: 13, color: 0x2979ff, clr: "#2979ff", role: "Défense/Hardening"},
  "red-team":     {index: 14, color: 0xff1744, clr: "#ff1744", role: "Tests Intrusion"}
};

// Symmetrical service positions (placed in a stack or central cluster)
var SERVICE_STATIONS = {
  "go-bus":      {pos: new THREE.Vector3(0, 0, 0),     color: 0x00d2ff, clr: "#00d2ff", role: "Bus d'événements (Hub)"},
  "postgresql":  {pos: new THREE.Vector3(0, -2.2, 0),  color: 0x3366ff, clr: "#5588cc", role: "Base de données (Stockage)"},
  "graphify":    {pos: new THREE.Vector3(0, 2.2, 0),   color: 0xff6d00, clr: "#ff8844", role: "Visualisation 3D (Moteur)"}
};

function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020205);
  scene.fog = new THREE.FogExp2(0x020205, 0.015);

  camera = new THREE.PerspectiveCamera(50, window.innerWidth/window.innerHeight, 0.1, 500);
  camera.position.set(0, 15, 20);

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  document.getElementById('app').appendChild(renderer.domElement);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.autoRotate = false; // Static network should NOT rotate automatically for readability
  controls.minDistance = 3;
  controls.maxDistance = 50;
  controls.target.set(0, 0, 0);

  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();

  // Blueprint digital hologram grid
  var grid = new THREE.GridHelper(30, 30, 0x00f0ff, 0x0f1b2d);
  grid.position.y = -1.2;
  grid.material.transparent = true;
  grid.material.opacity = 0.22;
  scene.add(grid);

  // Lighting
  var coreLight = new THREE.PointLight(0x00f0ff, 3, 30, 1.2);
  coreLight.position.set(0, 0, 0);
  scene.add(coreLight);
  scene.add(new THREE.AmbientLight(0x0a1020));
  var fill = new THREE.DirectionalLight(0x00aaff, 0.35);
  fill.position.set(5, 10, 5);
  scene.add(fill);

  // Background stars
  var sg = new THREE.BufferGeometry();
  var sp = new Float32Array(5000 * 3);
  for (var i = 0; i < 5000; i++) {
    var r = 50 + Math.random() * 100;
    var t = Math.random() * Math.PI * 2;
    var p = Math.acos(2 * Math.random() - 1);
    sp[i*3] = r * Math.sin(p) * Math.cos(t);
    sp[i*3+1] = r * Math.sin(p) * Math.sin(t);
    sp[i*3+2] = r * Math.cos(p);
  }
  sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  var starMat = new THREE.PointsMaterial({color: 0x3a5d8c, size: 0.35, transparent: true, opacity: 0.65});
  scene.add(new THREE.Points(sg, starMat));

  renderer.domElement.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);
  loadGraph();
}

function loadGraph() {
  fetch('/api/graph').then(function(r) { return r.json(); }).then(function(data) {
    buildStaticTopology(data);
    animate();
  });
}

function buildStaticTopology(data) {
  // Clear old lines
  edgeLines.forEach(function(el) {
    scene.remove(el.line);
    el.line.geometry.dispose();
    el.line.material.dispose();
  });
  edgeLines = [];

  var skillNodes = {};
  var agentNodes = {};
  var serviceNodes = {};
  var evaNode = null;

  for (var i = 0; i < data.nodes.length; i++) {
    var n = data.nodes[i];
    if (n.label === 'EVA') evaNode = n;
    else if (n.label === 'Agent') agentNodes[n.id] = n;
    else if (n.label === 'Service') serviceNodes[n.id] = n;
    else if (n.label === 'SkillDomain') skillNodes[n.id] = n;
  }

  // Map has_skill relationships
  var agentSkills = {};
  for (var key in agentNodes) agentSkills[key] = [];
  for (var i = 0; i < data.edges.length; i++) {
    var e = data.edges[i];
    if (e.relation === 'has_skill' && agentNodes[e.source] && skillNodes[e.target]) {
      agentSkills[e.source].push(skillNodes[e.target]);
    }
  }

  // === 1. BUILD EVA CORE (Top of Tower) ===
  var evaPos = new THREE.Vector3(0, 4.4, 0);
  if (!meshes['eva']) {
    var sun = new THREE.Mesh(
      new THREE.SphereGeometry(1.0, 32, 32),
      new THREE.MeshPhongMaterial({color: 0xffaa00, emissive: 0xff5500, emissiveIntensity: 0.5, shininess: 80})
    );
    sun.position.copy(evaPos);
    sun.userData = {name: evaNode ? evaNode.name : 'EVA', label: 'EVA', props: evaNode ? evaNode.properties : {}};
    scene.add(sun);
    meshes['eva'] = sun;

    // Glowing shield overlay
    var shield = new THREE.Mesh(
      new THREE.SphereGeometry(1.3, 16, 16),
      new THREE.MeshBasicMaterial({color: 0xff8800, wireframe: true, transparent: true, opacity: 0.08})
    );
    shield.position.copy(evaPos);
    scene.add(shield);

    // Label
    var sl = document.createElement('div');
    sl.className = 'node-label';
    sl.textContent = 'EVA Central AI';
    sl.style.color = '#ffaa00';
    sl.style.border = '1px solid rgba(255, 170, 0, 0.4)';
    document.body.appendChild(sl);
    sun.userData.labelEl = sl;
  }

  // === 2. BUILD CENTRAL SERVICE STATIONS (Central Tower Column) ===
  var svcKeys = Object.keys(serviceNodes);
  for (var i = 0; i < svcKeys.length; i++) {
    var svcId = svcKeys[i];
    var svcNode = serviceNodes[svcId];
    var sName = svcNode.name.toLowerCase();

    var scfg = null;
    if (sName.includes('bus')) scfg = SERVICE_STATIONS['go-bus'];
    else if (sName.includes('postgre')) scfg = SERVICE_STATIONS['postgresql'];
    else if (sName.includes('graphify')) scfg = SERVICE_STATIONS['graphify'];
    else {
      scfg = {pos: new THREE.Vector3(0, -1.2, 0), color: 0xd500f9, clr: "#d500f9", role: "Service Core"};
    }

    var station = meshes[svcId];
    if (!station) {
      if (sName.includes('postgre')) {
        // cylinder database rack
        var dbGroup = new THREE.Group();
        for (var c = 0; c < 3; c++) {
          var slice = new THREE.Mesh(
            new THREE.CylinderGeometry(0.5, 0.5, 0.35, 16),
            new THREE.MeshPhongMaterial({color: scfg.color, emissive: scfg.color, emissiveIntensity: 0.25})
          );
          slice.position.y = -0.45 * c + 0.45;
          dbGroup.add(slice);
        }
        dbGroup.position.copy(scfg.pos);
        scene.add(dbGroup);
        station = dbGroup;
      } else {
        // geometric icosahedron for bus/engine
        station = new THREE.Mesh(
          new THREE.IcosahedronGeometry(0.55, 0),
          new THREE.MeshPhongMaterial({color: scfg.color, emissive: scfg.color, emissiveIntensity: 0.35, flatShading: true})
        );
        station.position.copy(scfg.pos);
        scene.add(station);
      }
      meshes[svcId] = station;
    }
    station.userData = {
      id: svcId, name: svcNode.name, label: 'Service',
      props: { role: scfg.role, ...svcNode.properties },
      isStation: true,
      basePos: scfg.pos.clone()
    };

    var stl = station.userData.labelEl;
    if (!stl) {
      stl = document.createElement('div');
      stl.className = 'node-label';
      stl.textContent = svcNode.name;
      stl.style.color = scfg.clr;
      stl.style.border = '1px solid ' + scfg.clr + '44';
      document.body.appendChild(stl);
      station.userData.labelEl = stl;
    }
  }

  // === 3. BUILD AGENTS (Static Outer Hologram Circle) ===
  var agentKeys = Object.keys(agentNodes);
  var radius = 9.0;

  for (var i = 0; i < agentKeys.length; i++) {
    var agentId = agentKeys[i];
    var agentNode = agentNodes[agentId];
    var aName = agentNode.name.toLowerCase();

    // Map to planet config
    var pconfig = null;
    for (var pkey in AGENT_PLANETS) {
      if (aName.includes(pkey)) {
        pconfig = AGENT_PLANETS[pkey];
        break;
      }
    }
    if (!pconfig) {
      pconfig = {index: i, color: 0x90a4ae, clr: '#90a4ae', role: "Agent Autonome"};
    }

    // Static Position on XZ Circle
    var theta = (pconfig.index / 15) * Math.PI * 2;
    var staticPos = new THREE.Vector3(Math.cos(theta) * radius, 0, Math.sin(theta) * radius);

    var planet = meshes[agentId];
    if (!planet) {
      // Distinct glowing sphere
      planet = new THREE.Mesh(
        new THREE.SphereGeometry(0.38, 16, 16),
        new THREE.MeshPhongMaterial({color: pconfig.color, emissive: pconfig.color, emissiveIntensity: 0.28, shininess: 50})
      );
      planet.position.copy(staticPos);
      scene.add(planet);
      meshes[agentId] = planet;
    }
    planet.userData = {
      id: agentId, name: agentNode.name, label: 'Agent',
      props: { role: pconfig.role, ...agentNode.properties },
      isPlanet: true,
      basePos: staticPos.clone(),
      phase: i * 0.5 // animation offset
    };

    // Label
    var pl = planet.userData.labelEl;
    if (!pl) {
      pl = document.createElement('div');
      pl.className = 'node-label';
      pl.textContent = agentNode.name;
      pl.style.color = pconfig.clr;
      pl.style.border = '1px solid ' + pconfig.clr + '33';
      document.body.appendChild(pl);
      planet.userData.labelEl = pl;
    }

    // === BUILD SKILLS (Static Concentric Rings around each Agent) ===
    var skills = agentSkills[agentId] || [];
    var numMoons = Math.min(skills.length, 10);

    for (var mi = 0; mi < numMoons; mi++) {
      var skill = skills[mi];
      var skillDist = 1.0;
      var skillAngle = (mi / numMoons) * Math.PI * 2;
      
      var skillOffset = new THREE.Vector3(Math.cos(skillAngle) * skillDist, 0, Math.sin(skillAngle) * skillDist);
      var skillPos = staticPos.clone().add(skillOffset);

      var moon = meshes[skill.id];
      if (!moon) {
        // Cyber cube shape for skill nodes
        moon = new THREE.Mesh(
          new THREE.BoxGeometry(0.12, 0.12, 0.12),
          new THREE.MeshPhongMaterial({color: 0x00f0ff, emissive: 0x00f0ff, emissiveIntensity: 0.15})
        );
        moon.position.copy(skillPos);
        scene.add(moon);
        meshes[skill.id] = moon;
      }
      moon.userData = {
        id: skill.id, name: skill.name, label: 'SkillDomain',
        props: skill.properties,
        parentPlanet: planet,
        isMoon: true,
        offset: skillOffset.clone()
      };

      var ml = moon.userData.labelEl;
      if (!ml) {
        ml = document.createElement('div');
        ml.className = 'node-label';
        ml.textContent = skill.name;
        ml.style.color = '#718bb2';
        ml.style.fontSize = '8.5px';
        ml.style.border = '1px solid rgba(113, 139, 178, 0.2)';
        document.body.appendChild(ml);
        moon.userData.labelEl = ml;
      }
    }
  }

  // === 4. GENERATE PERMANENT DIGITAL WIRE PATHS (Connections) ===
  var busMesh = findMeshByName('go-bus');
  var dbMesh = findMeshByName('postgresql');

  // Draw wires from all agents to the Go-Bus (Hub-and-Spoke structure)
  if (busMesh) {
    for (var key in meshes) {
      var m = meshes[key];
      if (m.userData.isPlanet) {
        // Hub-and-Spoke link
        var geom = new THREE.BufferGeometry().setFromPoints([m.position, busMesh.position]);
        var mat = new THREE.LineBasicMaterial({color: 0x00aaff, transparent: true, opacity: 0.22});
        var line = new THREE.Line(geom, mat);
        scene.add(line);
        edgeLines.push({line: line, source: m, target: busMesh});
      }
    }
  }

  // Draw wire database link (Bus -> DB)
  if (busMesh && dbMesh) {
    var geom = new THREE.BufferGeometry().setFromPoints([busMesh.position, dbMesh.position]);
    var mat = new THREE.LineBasicMaterial({color: 0x00ff88, transparent: true, opacity: 0.4});
    var line = new THREE.Line(geom, mat);
    scene.add(line);
    edgeLines.push({line: line, source: busMesh, target: dbMesh});
  }

  // Draw wire AI link (Bus -> EVA)
  if (busMesh && meshes['eva']) {
    var geom = new THREE.BufferGeometry().setFromPoints([busMesh.position, meshes['eva'].position]);
    var mat = new THREE.LineBasicMaterial({color: 0xffaa00, transparent: true, opacity: 0.4});
    var line = new THREE.Line(geom, mat);
    scene.add(line);
    edgeLines.push({line: line, source: busMesh, target: meshes['eva']});
  }

  // General database edges (like dependencies or communications from edges.json)
  for (var i = 0; i < data.edges.length; i++) {
    var e = data.edges[i];
    var src = meshes[e.source];
    var tgt = meshes[e.target];
    // Avoid double linking with existing wires
    if (src && tgt && e.relation !== 'has_skill' && src !== busMesh && tgt !== busMesh) {
      var geom = new THREE.BufferGeometry().setFromPoints([src.position, tgt.position]);
      var color = 0x5577aa;
      var opacity = 0.15;
      if (e.relation === 'depends_on') { color = 0xff9100; opacity = 0.22; }
      else if (e.relation === 'communicates_with') { color = 0x00ff88; opacity = 0.25; }
      
      var mat = new THREE.LineBasicMaterial({color: color, transparent: true, opacity: opacity});
      var line = new THREE.Line(geom, mat);
      scene.add(line);
      edgeLines.push({line: line, source: src, target: tgt});
    }
  }

  // Stats bar
  var sb = document.getElementById('stats-bar');
  sb.innerHTML = '<div>Topologie: <span class="val">Matricielle / Étoile</span></div>' +
                 '<div>Agents: <span class="val">' + agentKeys.length + '</span></div>' +
                 '<div>Skills: <span class="val">' + Object.keys(skillNodes).length + '</span></div>' +
                 '<div>Services: <span class="val">' + svcKeys.length + '</span></div>';

  // Legend UI
  var leg = document.getElementById('legend-items');
  leg.innerHTML = '';
  var items = [
    {clr: '#ffaa00', label: 'EVA Core (IA)', count: 1},
    {clr: '#00f0ff', label: 'Agents (Platform)', count: agentKeys.length},
    {clr: '#00aaff', label: 'Skills (Matrices)', count: Object.keys(skillNodes).length},
    {clr: '#ff8844', label: 'Services (Core API)', count: svcKeys.length}
  ];
  for (var i = 0; i < items.length; i++) {
    var d = document.createElement('div');
    d.className = 'item';
    d.innerHTML = '<span class="dot" style="background:' + items[i].clr + ';color:' + items[i].clr + '"></span>' + items[i].label + '<span class="count">' + items[i].count + '</span>';
    leg.appendChild(d);
  }
}

function updatePositions(t) {
  for (var key in meshes) {
    var m = meshes[key];
    var u = m.userData;

    if (u.isPlanet && u.basePos) {
      // Static placement with subtle breathing animation (floating vertically)
      m.position.x = u.basePos.x;
      m.position.z = u.basePos.z;
      m.position.y = u.basePos.y + Math.sin(t * 1.5 + u.phase) * 0.18;
      m.rotation.y = t * 0.25;
    }

    if (u.isStation && u.basePos) {
      m.position.x = u.basePos.x;
      m.position.z = u.basePos.z;
      m.position.y = u.basePos.y + Math.sin(t * 1.2) * 0.08;
      m.rotation.y = t * 0.35;
      m.rotation.x = t * 0.15;
    }

    if (u.isMoon && u.offset && u.parentPlanet) {
      // Position moon statically around the breathing planet position
      m.position.copy(u.parentPlanet.position).add(u.offset);
      // Subtle float
      m.position.y += Math.sin(t * 2.0 + u.offset.x) * 0.04;
      m.rotation.y = t * 0.5;
    }
  }

  // Update permanent circuit wire paths dynamically
  for (var i = 0; i < edgeLines.length; i++) {
    var el = edgeLines[i];
    var posAttr = el.line.geometry.attributes.position;
    posAttr.setXYZ(0, el.source.position.x, el.source.position.y, el.source.position.z);
    posAttr.setXYZ(1, el.target.position.x, el.target.position.y, el.target.position.z);
    posAttr.needsUpdate = true;
    el.line.geometry.computeBoundingSphere();
  }
}

function updateLabels() {
  for (var key in meshes) {
    var m = meshes[key];
    if (m.userData.labelEl) {
      var pos = m.position.clone();
      pos.project(camera);
      if (pos.z < 1) {
        var x = (pos.x * 0.5 + 0.5) * window.innerWidth;
        var y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
        m.userData.labelEl.style.left = x + 'px';
        m.userData.labelEl.style.top = y + 'px';
        
        var dist = camera.position.distanceTo(m.position);
        if (m.userData.isMoon && dist > 14) {
          m.userData.labelEl.style.opacity = '0';
          m.userData.labelEl.style.pointerEvents = 'none';
        } else if (dist > 42) {
          m.userData.labelEl.style.opacity = '0';
          m.userData.labelEl.style.pointerEvents = 'none';
        } else {
          m.userData.labelEl.style.opacity = '1';
          m.userData.labelEl.style.pointerEvents = 'auto';
        }
      } else {
        m.userData.labelEl.style.opacity = '0';
      }
    }
  }
}

function onClick(event) {
  var rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);

  var clickable = scene.children.filter(function(c) {
    return c.isMesh && c.geometry && (c.geometry.type === 'SphereGeometry' || c.geometry.type === 'IcosahedronGeometry');
  });
  // also add databases Cylinders
  scene.traverse(function(c) {
    if (c.parent && c.parent.userData && c.parent.userData.isStation) clickable.push(c);
  });

  var hits = raycaster.intersectObjects(clickable);
  
  if (hits.length > 0) {
    var hitObj = hits[0].object;
    // Handle database cylinder group hit redirection
    if (hitObj.parent && hitObj.parent.userData && hitObj.parent.userData.name) {
      hitObj = hitObj.parent;
    }
    
    if (hitObj.userData.name) {
      document.getElementById('info-name').textContent = hitObj.userData.name;
      var tag = document.getElementById('info-tag');
      tag.textContent = hitObj.userData.label;
      
      var clr = '#ffaa00';
      if (hitObj.userData.label === 'Agent') clr = '#00f0ff';
      else if (hitObj.userData.label === 'SkillDomain') clr = '#00aaff';
      else if (hitObj.userData.label === 'Service') clr = '#ff6d00';
      
      tag.style.background = clr + '22';
      tag.style.color = clr;
      
      var p = hitObj.userData.props || {};
      var html = '';
      for (var k in p) { 
        var val = typeof p[k] === 'object' ? JSON.stringify(p[k]) : p[k];
        html += '<div><span class="k">' + k + '</span> <span>' + val + '</span></div>'; 
      }
      document.getElementById('info-props').innerHTML = html || 'Aucune propriété';
      document.getElementById('info').classList.add('visible');
      
      if (selected && selected.material && selected.material.emissiveIntensity) {
        selected.material.emissiveIntensity = selected.userData.isPlanet ? 0.28 : 0.35;
      }
      selected = hitObj;
      if (selected.material && selected.material.emissiveIntensity) {
        selected.material.emissiveIntensity = 0.7;
      }
    }
  } else {
    document.getElementById('info').classList.remove('visible');
    if (selected && selected.material && selected.material.emissiveIntensity) { 
      selected.material.emissiveIntensity = selected.userData.isPlanet ? 0.28 : 0.35;
      selected = null; 
    }
  }
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
  requestAnimationFrame(animate);
  var dt = clock.getDelta();
  animTime += dt;
  
  controls.update();
  updatePositions(animTime);
  
  updateParticles(dt);
  updateFlashes(dt);
  
  if (selected && selected.material && selected.material.emissiveIntensity) {
    selected.material.emissiveIntensity = 0.55 + 0.2 * Math.sin(Date.now() * 0.005);
  }
  renderer.render(scene, camera);
  updateLabels();
}

// === NETWORKING TRAFFIC SIMULATOR & FLASH ANIMATION ===
function createParticle(src, tgt, status) {
  var color = 0x00f0ff;
  if (status === 'failed') color = 0xff1744;
  else if (status === 'timeout') color = 0xff9100;
  else if (status === 'done' || status === 'success') color = 0x00ff88;
  
  var mat = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.95,
    blending: THREE.AdditiveBlending
  });
  
  var geom = new THREE.SphereGeometry(0.12, 8, 8);
  var mesh = new THREE.Mesh(geom, mat);
  mesh.position.copy(src.position);
  scene.add(mesh);
  
  // High-speed data trail line
  var trailGeom = new THREE.BufferGeometry();
  var trailPoints = [];
  for (var i = 0; i < 6; i++) {
    trailPoints.push(src.position.clone());
  }
  trailGeom.setFromPoints(trailPoints);
  var trailMat = new THREE.LineBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.5,
    blending: THREE.AdditiveBlending
  });
  var trail = new THREE.Line(trailGeom, trailMat);
  scene.add(trail);
  
  activeParticles.push({
    mesh: mesh,
    trail: trail,
    trailPoints: trailPoints,
    source: src,
    target: tgt,
    progress: 0,
    speed: 0.7 + Math.random() * 0.4, // rapid delivery (takes ~1 - 1.4s)
    color: color,
    arcHeight: 1.0 + Math.random() * 1.5
  });
}

function updateParticles(dt) {
  for (var i = activeParticles.length - 1; i >= 0; i--) {
    var p = activeParticles[i];
    p.progress += p.speed * dt;
    if (p.progress >= 1) {
      scene.remove(p.mesh);
      p.mesh.geometry.dispose();
      p.mesh.material.dispose();
      
      scene.remove(p.trail);
      p.trail.geometry.dispose();
      p.trail.material.dispose();
      
      activeParticles.splice(i, 1);
      
      triggerImpactGlow(p.target, p.color);
    } else {
      var pos = new THREE.Vector3().lerpVectors(p.source.position, p.target.position, p.progress);
      pos.y += Math.sin(p.progress * Math.PI) * p.arcHeight;
      p.mesh.position.copy(pos);
      
      p.trailPoints.shift();
      p.trailPoints.push(pos.clone());
      p.trail.geometry.setFromPoints(p.trailPoints);
    }
  }
}

function triggerImpactGlow(targetMesh, color) {
  if (!targetMesh) return;
  
  // Handle database cylinders stack animation
  if (targetMesh.children && targetMesh.children.length > 0) {
    targetMesh.children.forEach(function(child) {
      if (child.material) triggerIndividualGlow(child);
    });
  } else {
    triggerIndividualGlow(targetMesh);
  }
}

function triggerIndividualGlow(mesh) {
  if (!mesh.material) return;
  var mat = mesh.material;
  var originalIntensity = mesh.userData.isPlanet ? 0.28 : 0.35;
  mat.emissiveIntensity = 2.4; // Flash
  
  var origScale = mesh.scale.x;
  mesh.scale.set(origScale * 1.25, origScale * 1.25, origScale * 1.25);
  
  activeFlashes.push({
    mesh: mesh,
    originalIntensity: originalIntensity,
    origScale: origScale,
    progress: 0,
    update: function(dt) {
      this.progress += dt * 5.0; // 0.2s duration
      if (this.progress >= 1) {
        this.mesh.material.emissiveIntensity = this.originalIntensity;
        this.mesh.scale.set(this.origScale, this.origScale, this.origScale);
        return true;
      }
      this.mesh.material.emissiveIntensity = this.originalIntensity + (1.0 - this.progress) * 2.0;
      var s = this.origScale * (1.0 + (1.0 - this.progress) * 0.25);
      this.mesh.scale.set(s, s, s);
      return false;
    }
  });
}

function updateFlashes(dt) {
  for (var i = activeFlashes.length - 1; i >= 0; i--) {
    var f = activeFlashes[i];
    var done = f.update(dt);
    if (done) activeFlashes.splice(i, 1);
  }
}

function findMeshByName(name) {
  if (!name) return null;
  name = name.toLowerCase();
  for (var key in meshes) {
    var m = meshes[key];
    var mName = m.userData.name ? m.userData.name.toLowerCase() : '';
    if (mName === name || mName.includes(name) || name.includes(mName)) {
      return m;
    }
  }
  return null;
}

function triggerPacketFlow(p) {
  var srcName = p.source ? p.source.toLowerCase() : '';
  var topic = p.topic ? p.topic.toLowerCase() : '';
  
  var srcMesh = findMeshByName(srcName);
  var busMesh = findMeshByName('go-bus');
  var dbMesh = findMeshByName('postgresql');
  var evaMesh = meshes['eva'];

  if (!srcMesh) srcMesh = busMesh || evaMesh;

  // Visual flows:
  // 1. From Agent to Go-Bus (normal event publish)
  // 2. From Go-Bus to DB (if it's persisted, e.g. ctf/finance)
  // 3. From Go-Bus to EVA (system critical tick)
  // 4. From Go-Bus to targeted agent (adam:mission dispatch)
  
  if (topic === 'adam:mission' && p.payload && p.payload.agent) {
    var targetAgent = findMeshByName(p.payload.agent);
    if (targetAgent && busMesh) {
      // First agent to Bus
      createParticle(srcMesh, busMesh, p.status);
      // Then Bus to target agent
      setTimeout(function() { createParticle(busMesh, targetAgent, p.status); }, 400);
    }
  } else if (topic.includes('finance') || topic.includes('ctf') || topic.includes('packet')) {
    if (srcMesh && busMesh && dbMesh) {
      // First Agent to Bus
      createParticle(srcMesh, busMesh, p.status);
      // Then Bus to DB
      setTimeout(function() { createParticle(busMesh, dbMesh, p.status); }, 400);
    }
  } else {
    // Normal bus communication
    if (srcMesh && busMesh) {
      createParticle(srcMesh, busMesh, p.status);
    }
  }
}

function fetchPackets() {
  fetch('/api/packets').then(function(r) { return r.json(); }).then(function(d) {
    if (!d.packets || !d.packets.length) return;
    
    // Sort oldest to newest to replay
    var pkts = d.packets.slice().reverse();
    pkts.forEach(function(p) {
      var timeStr = p.timestamp || p.time || '';
      if (!lastPacketTime || timeStr > lastPacketTime) {
        lastPacketTime = timeStr;
        triggerPacketFlow(p);
      }
    });

    // Update list UI
    var c = document.getElementById('packet-list');
    c.innerHTML = '';
    var displayPkts = d.packets.slice(0, 15);
    displayPkts.forEach(function(p) {
      var div = document.createElement('div');
      div.className = 'pkt';
      var timeStr = p.timestamp || p.time || '';
      var t = timeStr.slice(11, 19) || '--:--:--';
      var st = p.status || 'done';
      
      var stClr = '#00ff88';
      if (st === 'failed') stClr = '#ff1744';
      else if (st === 'timeout') stClr = '#ff9100';
      
      div.innerHTML = '<span class="t">' + t + '</span>' +
                      '<span class="s">' + p.source + '</span>' +
                      '<span class="top">' + p.topic + '</span>' +
                      '<span class="st" style="color:' + stClr + ';border-color:' + stClr + '22;background:' + stClr + '06">' + st + '</span>';
      c.appendChild(div);
    });
  }).catch(function(e) {});
}

function simulateEvent() {
  fetch('/api/simulate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  }).then(function(r) { return r.json(); }).then(function(d) {
    if (d.status === 'ok') {
      console.log('Simulated:', d.simulated);
      // Instantly poll packets to show simulated flow
      setTimeout(fetchPackets, 150);
    }
  }).catch(function(e) {});
}

// Initial setup
setInterval(function() { loadGraph(); }, 25000);
init();
setInterval(fetchPackets, 1500);
fetchPackets();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
