#!/usr/bin/env python3
"""Graphify 3D V5 - Live Activity: Solar System + real-time agent activity"""
from flask import Flask, jsonify
import psycopg2, json, os, urllib.request, time, threading

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:***@postgres:5432/adam")
BUS_URL = os.environ.get("BUS_URL", "http://go-bus:8086")

nodes_cache = {"nodes": [], "edges": [], "ts": 0}
packets_cache = []
agents_status = {}
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
        time.sleep(15)

def refresh_packets():
    while True:
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=15&topic=adam:packet")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    with lock:
                        packets_cache.clear()
                        packets_cache.extend(data)
        except Exception:
            pass
        time.sleep(3)

threading.Thread(target=refresh_graph, daemon=True).start()
threading.Thread(target=refresh_packets, daemon=True).start()

@app.route("/api/graph")
def get_graph():
    with lock:
        return jsonify(nodes_cache)

@app.route("/api/packets")
def get_packets():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=15&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return jsonify({"packets": data})
            return jsonify({"packets": data.get("events", [])})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

@app.route("/api/agents/status")
def get_agents_status():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            packets = data if isinstance(data, list) else data.get("events", [])
            agents = {}
            now = time.time()
            for p in packets:
                src = p.get("source", "")
                ts = p.get("timestamp", "")
                if src:
                    agents[src] = {"name": src, "active": True, "status": "working",
                                   "text": p.get("payload", {}).get("action", "working"),
                                   "timestamp": ts}
            return jsonify({"agents": agents, "packets": packets[:10]})
    except Exception as e:
        return jsonify({"agents": {}, "packets": [], "error": str(e)})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM Galaxy - Live</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#020208;color:#e8e8f0;font-family:'SF Pro Display','Segoe UI',system-ui,sans-serif;overflow:hidden}
#app{width:100vw;height:100vh}
#topbar{position:fixed;top:0;left:0;right:0;height:44px;background:linear-gradient(180deg,rgba(2,2,8,0.95),rgba(2,2,8,0.3));display:flex;align-items:center;justify-content:space-between;padding:0 24px;z-index:100;backdrop-filter:blur(10px);border-bottom:1px solid rgba(68,102,136,0.1)}
#topbar .logo{display:flex;align-items:center;gap:10px}
#topbar .logo .dot{width:8px;height:8px;border-radius:50%;background:#ffaa00;box-shadow:0 0 12px #ffaa00;animation:pulse 2s infinite}
#topbar .logo span{font-size:13px;font-weight:600;letter-spacing:0.5px}
#topbar .stats{display:flex;gap:16px;font-size:11px;color:#5577aa}
#topbar .stats .val{color:#e8e8f0;font-weight:600}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}

#info{position:fixed;top:60px;left:20px;z-index:50;background:rgba(5,5,15,0.92);padding:14px 18px;border-radius:12px;border:1px solid rgba(68,102,136,0.2);max-width:280px;pointer-events:none;opacity:0;transition:all 0.3s;transform:translateY(-5px)}
#info.visible{opacity:1;transform:translateY(0)}
#info h3{margin:0 0 2px;font-size:15px;font-weight:600}
#info .tag{display:inline-block;font-size:9px;padding:2px 8px;border-radius:10px;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600}
#info .props{font-size:11px;line-height:1.6;color:#88aacc}
#info .props .k{color:#5577aa;font-size:10px}
#info .status-live{font-size:11px;color:#00ff88;margin-top:8px;display:flex;align-items:center;gap:5px}
#info .status-live .dot{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:pulse 1s infinite}

#legend{position:fixed;bottom:20px;left:20px;z-index:50;background:rgba(5,5,15,0.92);padding:10px 14px;border-radius:10px;border:1px solid rgba(68,102,136,0.12)}
#legend h4{font-size:10px;color:#5577aa;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
#legend .item{display:flex;align-items:center;gap:8px;font-size:11px;padding:2px 0;color:#aabbcc}
#legend .dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;box-shadow:0 0 6px currentColor}
#legend .count{color:#446688;font-size:9px;margin-left:auto}

#packet-stream{position:fixed;bottom:20px;right:20px;z-index:50;background:rgba(5,5,15,0.92);padding:12px;border-radius:10px;border:1px solid rgba(68,102,136,0.12);width:360px;max-height:320px;overflow-y:auto}
#packet-stream::-webkit-scrollbar{width:3px}
#packet-stream::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}
#packet-stream h4{font-size:10px;color:#5577aa;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:6px}
#packet-stream .live{width:5px;height:5px;border-radius:50%;background:#ff4466;animation:pulse 1s infinite}
.pkt{color:#88aacc;padding:4px 0;border-bottom:1px solid rgba(68,102,136,0.06);font-size:10px;font-family:'SF Mono',Menlo,monospace;display:flex;align-items:center;gap:5px}
.pkt .t{color:#446688;min-width:50px}
.pkt .s{color:#00ff88;font-weight:600;min-width:65px}
.pkt .top{color:#aaccff;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pkt .st{font-size:8px;padding:1px 4px;border-radius:3px;font-weight:600;text-transform:uppercase}

#agent-panel{position:fixed;top:60px;right:20px;z-index:50;background:rgba(5,5,15,0.92);padding:12px;border-radius:10px;border:1px solid rgba(68,102,136,0.12);width:220px;max-height:50vh;overflow-y:auto}
#agent-panel::-webkit-scrollbar{width:3px}
#agent-panel::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}
#agent-panel h4{font-size:10px;color:#5577aa;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px}
.agent-row{display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid rgba(68,102,136,0.06);font-size:11px}
.agent-row .dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.agent-row .dot.active{background:#00ff88;box-shadow:0 0 6px #00ff88;animation:pulse 1.5s infinite}
.agent-row .dot.idle{background:#446688}
.agent-row .name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.agent-row .status{font-size:9px;color:#446688}

.node-label{position:absolute;font-size:10px;font-weight:500;text-shadow:0 0 4px #000,0 0 8px #000;background:rgba(2,2,8,0.8);padding:2px 6px;border-radius:4px;pointer-events:none;white-space:nowrap;z-index:5;transform:translate(-50%,-50%)}
#hint{position:fixed;bottom:20px;right:400px;z-index:50;font-size:10px;color:#334455;line-height:1.8;text-align:right}
.activity-indicator{position:absolute;font-size:9px;color:#00ff88;background:rgba(0,255,136,0.15);padding:1px 6px;border-radius:3px;pointer-events:none;z-index:6;transform:translate(-50%,-100%);animation:fadeUp 2s infinite}
@keyframes fadeUp{0%{opacity:0;transform:translate(-50%,-100%) translateY(5px)}20%{opacity:1}80%{opacity:1}100%{opacity:0;transform:translate(-50%,-100%) translateY(-5px)}}
</style>
</head>
<body>
<div id="app"></div>
<div id="topbar">
  <div class="logo"><div class="dot"></div><span>ADAM Galaxy</span></div>
  <div class="stats" id="stats-bar"></div>
</div>
<div id="info">
  <h3 id="info-name">-</h3>
  <div class="tag" id="info-tag"></div>
  <div class="props" id="info-props"></div>
  <div class="status-live" id="info-status" style="display:none"><span class="dot"></span><span id="info-status-text">Actif</span></div>
</div>
<div id="agent-panel"><h4>Agents actifs</h4><div id="agent-list"></div></div>
<div id="legend"><h4>Systeme</h4><div id="legend-items"></div></div>
<div id="packet-stream"><h4><span class="live"></span>Flux temps reel</h4></div>
<div id="hint">Glisser: orbiter<br>Molette: zoom<br>Clic: details</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var scene, camera, renderer, controls;
var meshes = {};
var orbits = [];
var raycaster, pointer;
var selected = null;
var animTime = 0;
var lastPackets = [];
var agentActivity = {};

var AGENT_PLANETS = {
  "adam-praetor":   {dist: 5, angle: 0,    speed: 0.15, size: 0.5, color: 0xff4444, clr: "#ff4444"},
  "adam-critic":    {dist: 6, angle: 0.8,  speed: 0.12, size: 0.45, color: 0xffdd00, clr: "#ffdd00"},
  "adam-sentinel":  {dist: 7, angle: 1.6,  speed: 0.10, size: 0.55, color: 0x00ddff, clr: "#00ddff"},
  "adam-monitor":   {dist: 8, angle: 2.4,  speed: 0.08, size: 0.5, color: 0xff8800, clr: "#ff8800"},
  "adam-blue":      {dist: 9, angle: 3.2,  speed: 0.07, size: 0.48, color: 0x4488ff, clr: "#4488ff"},
  "adam-red":       {dist: 9.5, angle: 4.0, speed: 0.065, size: 0.48, color: 0xff4444, clr: "#ff4444"},
  "adam-doctor":    {dist: 10, angle: 4.8, speed: 0.06, size: 0.42, color: 0xaa66ff, clr: "#aa66ff"},
  "adam-cicd":      {dist: 6.5, angle: 5.6, speed: 0.11, size: 0.4, color: 0xffffff, clr: "#ffffff"},
  "adam-scribe":    {dist: 7.5, angle: 6.4, speed: 0.09, size: 0.4, color: 0x88ccff, clr: "#88ccff"},
  "adam-treasurer": {dist: 8.5, angle: 0.4, speed: 0.075, size: 0.38, color: 0xffaa00, clr: "#ffaa00"},
  "adam-social":    {dist: 5.5, angle: 1.2, speed: 0.14, size: 0.38, color: 0xff66aa, clr: "#ff66aa"},
  "adam-rag":       {dist: 10.5, angle: 2.0, speed: 0.055, size: 0.42, color: 0x44ffaa, clr: "#44ffaa"},
  "adam-viz":       {dist: 11, angle: 2.8, speed: 0.05, size: 0.45, color: 0x88ffaa, clr: "#88ffaa"},
  "adam-chat":      {dist: 7, angle: 5.2, speed: 0.10, size: 0.38, color: 0xaa88ff, clr: "#aa88ff"}
};

var SERVICE_STATIONS = {
  "go-bus":      {dist: 3.5, angle: 0.5, color: 0x00aaff, clr: "#00aaff", size: 0.35},
  "postgresql":  {dist: 3.5, angle: 2.5, color: 0x3366aa, clr: "#5588cc", size: 0.35},
  "graphify":    {dist: 3.5, angle: 4.5, color: 0xff8844, clr: "#ff8844", size: 0.35}
};

function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x020208);
  scene.fog = new THREE.FogExp2(0x020208, 0.010);

  camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 500);
  camera.position.set(0, 20, 25);

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  document.getElementById('app').appendChild(renderer.domElement);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.25;
  controls.minDistance = 3;
  controls.maxDistance = 50;

  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();

  // Lighting
  var sunLight = new THREE.PointLight(0xffaa44, 2.5, 50, 1.5);
  sunLight.position.set(0, 0, 0);
  scene.add(sunLight);
  scene.add(new THREE.AmbientLight(0x111122));
  var fill = new THREE.DirectionalLight(0x4466aa, 0.3);
  fill.position.set(10, 10, 10);
  scene.add(fill);

  // Stars
  var sg = new THREE.BufferGeometry();
  var sp = new Float32Array(6000);
  for (var i = 0; i < 6000; i++) {
    var r = 50 + Math.random() * 200;
    var t = Math.random() * Math.PI * 2;
    var p = Math.acos(2 * Math.random() - 1);
    sp[i*3] = r * Math.sin(p) * Math.cos(t);
    sp[i*3+1] = r * Math.sin(p) * Math.sin(t);
    sp[i*3+2] = r * Math.cos(p);
  }
  sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({color: 0x445577, size: 0.4, transparent: true, opacity: 0.7, sizeAttenuation: true})));

  renderer.domElement.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);
  loadGraph();
}

function loadGraph() {
  fetch('/api/graph').then(function(r) { return r.json(); }).then(function(data) {
    buildSolarSystem(data);
    animate();
    fetchAgentStatus();
  });
}

function buildSolarSystem(data) {
  var skillNodes = {};
  var agentNodes = {};
  var serviceNodes = {};
  var evaNode = null;
  var agentSkills = {};

  for (var i = 0; i < data.nodes.length; i++) {
    var n = data.nodes[i];
    if (n.label === 'EVA') evaNode = n;
    else if (n.label === 'Agent') agentNodes[n.id] = n;
    else if (n.label === 'Service') serviceNodes[n.id] = n;
    else if (n.label === 'SkillDomain') { skillNodes[n.id] = n; }
  }

  // Map skills to agents
  for (var key in agentNodes) { agentSkills[key] = []; }
  for (var i = 0; i < data.edges.length; i++) {
    var e = data.edges[i];
    if (e.relation === 'has_skill' && agentNodes[e.source] && skillNodes[e.target]) {
      agentSkills[e.source].push(skillNodes[e.target]);
    }
  }

  // === SUN (EVA) ===
  var sunSize = 1.5;
  var sun = new THREE.Mesh(
    new THREE.SphereGeometry(sunSize, 48, 48),
    new THREE.MeshBasicMaterial({color: 0xffaa00})
  );
  sun.userData = {name: evaNode ? evaNode.name : 'EVA', label: 'EVA', props: evaNode ? evaNode.properties : {}};
  scene.add(sun);
  meshes['eva'] = sun;

  // Sun corona
  for (var ci = 0; ci < 4; ci++) {
    var corona = new THREE.Mesh(
      new THREE.SphereGeometry(sunSize * (1.3 + ci * 0.3), 32, 32),
      new THREE.MeshBasicMaterial({color: 0xffaa00, transparent: true, opacity: 0.08 - ci * 0.015, side: THREE.BackSide})
    );
    scene.add(corona);
  }

  // Sun glow
  var glowCanvas = document.createElement('canvas');
  glowCanvas.width = 256; glowCanvas.height = 256;
  var gctx = glowCanvas.getContext('2d');
  var grad = gctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  grad.addColorStop(0, 'rgba(255,170,0,0.8)');
  grad.addColorStop(0.3, 'rgba(255,140,0,0.4)');
  grad.addColorStop(1, 'rgba(255,100,0,0)');
  gctx.fillStyle = grad;
  gctx.fillRect(0, 0, 256, 256);
  var glowTex = new THREE.Texture(glowCanvas);
  glowTex.needsUpdate = true;
  var sunGlow = new THREE.Sprite(new THREE.SpriteMaterial({map: glowTex, blending: THREE.AdditiveBlending, transparent: true}));
  sunGlow.scale.set(7, 7, 1);
  scene.add(sunGlow);

  // Sun label
  var sl = document.createElement('div');
  sl.className = 'node-label';
  sl.textContent = 'EVA';
  sl.style.color = '#ffaa00';
  sl.style.fontSize = '14px';
  sl.style.fontWeight = '700';
  document.body.appendChild(sl);
  sun.userData.labelEl = sl;

  // === PLANETS (Agents) ===
  var agentKeys = Object.keys(agentNodes);
  var planetIndex = 0;

  for (var i = 0; i < agentKeys.length; i++) {
    var agentId = agentKeys[i];
    var agentNode = agentNodes[agentId];
    var pconfig = null;
    for (var pkey in AGENT_PLANETS) {
      if (agentNode.name.toLowerCase().includes(pkey.replace('adam-', ''))) {
        pconfig = AGENT_PLANETS[pkey];
        break;
      }
    }
    if (!pconfig) {
      pconfig = {dist: 5 + planetIndex * 0.8, angle: planetIndex * 0.5, speed: 0.1 - planetIndex * 0.005, size: 0.4, color: 0x888888, clr: '#888'};
    }

    // Orbit ring
    var ringGeom = new THREE.RingGeometry(pconfig.dist - 0.02, pconfig.dist + 0.02, 128);
    var ring = new THREE.Mesh(ringGeom, new THREE.MeshBasicMaterial({color: pconfig.color, transparent: true, opacity: 0.08, side: THREE.DoubleSide}));
    ring.rotation.x = Math.PI / 2;
    scene.add(ring);
    orbits.push(ring);

    // Planet
    var planet = new THREE.Mesh(
      new THREE.SphereGeometry(pconfig.size, 24, 24),
      new THREE.MeshPhongMaterial({color: pconfig.color, emissive: pconfig.color, emissiveIntensity: 0.2, shininess: 60})
    );
    planet.userData = {
      id: agentId, name: agentNode.name, label: 'Agent',
      props: agentNode.properties,
      orbit: {dist: pconfig.dist, angle: pconfig.angle, speed: pconfig.speed},
      isPlanet: true
    };
    scene.add(planet);
    meshes[agentId] = planet;

    // Planet glow (bigger when active)
    var pglow = new THREE.Mesh(
      new THREE.SphereGeometry(pconfig.size * 1.8, 16, 16),
      new THREE.MeshBasicMaterial({color: pconfig.color, transparent: true, opacity: 0.08})
    );
    planet.userData.glow = pglow;
    scene.add(pglow);

    // Planet label
    var pl = document.createElement('div');
    pl.className = 'node-label';
    pl.textContent = agentNode.name;
    pl.style.color = pconfig.clr;
    document.body.appendChild(pl);
    planet.userData.labelEl = pl;

    // Activity indicator
    var ai = document.createElement('div');
    ai.className = 'activity-indicator';
    ai.textContent = '...';
    ai.style.color = pconfig.clr;
    ai.style.borderColor = pconfig.clr + '44';
    ai.style.display = 'none';
    document.body.appendChild(ai);
    planet.userData.activityEl = ai;

    // === MOONS (Skills) ===
    var skills = agentSkills[agentId] || [];
    var numMoons = Math.min(skills.length, 12);

    for (var mi = 0; mi < numMoons; mi++) {
      var skill = skills[mi];
      var moonDist = pconfig.size + 0.35 + (mi % 5) * 0.22;
      var moonAngle = (mi / numMoons) * Math.PI * 2;
      var moonSpeed = 0.4 + Math.random() * 0.3;
      var moonSize = 0.06 + Math.random() * 0.05;

      var moon = new THREE.Mesh(
        new THREE.SphereGeometry(moonSize, 12, 12),
        new THREE.MeshPhongMaterial({color: 0x4488ff, emissive: 0x4488ff, emissiveIntensity: 0.15})
      );
      moon.userData = {
        id: skill.id, name: skill.name, label: 'SkillDomain',
        props: skill.properties,
        parentPlanet: planet,
        orbit: {dist: moonDist, angle: moonAngle, speed: moonSpeed, parentDist: pconfig.dist, parentAngle: pconfig.angle, parentSpeed: pconfig.speed},
        isMoon: true
      };
      scene.add(moon);
      meshes[skill.id] = moon;

      var ml = document.createElement('div');
      ml.className = 'node-label';
      ml.textContent = skill.name;
      ml.style.color = '#5588cc';
      ml.style.fontSize = '9px';
      document.body.appendChild(ml);
      moon.userData.labelEl = ml;
    }
    planetIndex++;
  }

  // === SERVICES (Stations) ===
  var svcKeys = Object.keys(serviceNodes);
  for (var i = 0; i < svcKeys.length; i++) {
    var svcId = svcKeys[i];
    var svcNode = serviceNodes[svcId];
    var scfg = SERVICE_STATIONS['go-bus'];
    if (svcNode.name.includes('Graph')) scfg = SERVICE_STATIONS['graphify'];
    if (svcNode.name.includes('Postgre')) scfg = SERVICE_STATIONS['postgresql'];

    var station = new THREE.Mesh(
      new THREE.IcosahedronGeometry(scfg.size, 0),
      new THREE.MeshPhongMaterial({color: scfg.color, emissive: scfg.color, emissiveIntensity: 0.25, flatShading: true})
    );
    station.userData = {
      id: svcId, name: svcNode.name, label: 'Service',
      props: svcNode.properties,
      orbit: {dist: scfg.dist, angle: scfg.angle, speed: 0.15 + i * 0.05},
      isStation: true
    };
    scene.add(station);
    meshes[svcId] = station;

    var stl = document.createElement('div');
    stl.className = 'node-label';
    stl.textContent = svcNode.name;
    stl.style.color = scfg.clr;
    document.body.appendChild(stl);
    station.userData.labelEl = stl;
  }

  // Stats bar
  var sb = document.getElementById('stats-bar');
  sb.innerHTML = '<div>Soleil: <span class="val">EVA</span></div>' +
                 '<div>Planetes: <span class="val">' + agentKeys.length + '</span></div>' +
                 '<div>Skills: <span class="val">' + Object.keys(skillNodes).length + '</span></div>' +
                 '<div>Services: <span class="val">' + svcKeys.length + '</span></div>';

  // Legend
  var leg = document.getElementById('legend-items');
  leg.innerHTML = '';
  var items = [
    {clr: '#ffaa00', label: 'EVA (Soleil)', count: 1},
    {clr: '#00ff88', label: 'Agents (Planetes)', count: agentKeys.length},
    {clr: '#4488ff', label: 'Skills (Satellites)', count: Object.keys(skillNodes).length},
    {clr: '#ff8844', label: 'Services (Stations)', count: svcKeys.length}
  ];
  for (var i = 0; i < items.length; i++) {
    var d = document.createElement('div');
    d.className = 'item';
    d.innerHTML = '<span class="dot" style="background:' + items[i].clr + ';color:' + items[i].clr + '"></span>' + items[i].label + '<span class="count">' + items[i].count + '</span>';
    leg.appendChild(d);
  }

  console.log('Galaxy V5 built: ' + data.nodes.length + ' nodes');
}

function updatePositions(t) {
  for (var key in meshes) {
    var m = meshes[key];
    var u = m.userData;

    if (u.isPlanet && u.orbit) {
      var angle = u.orbit.angle + t * u.orbit.speed;
      m.position.set(
        Math.cos(angle) * u.orbit.dist,
        Math.sin(t * u.orbit.speed * 0.3) * 0.5,
        Math.sin(angle) * u.orbit.dist
      );
      if (u.glow) u.glow.position.copy(m.position);

      // Activity pulse
      if (agentActivity[u.id]) {
        var pulse = 0.5 + 0.5 * Math.sin(Date.now() * 0.005);
        m.material.emissiveIntensity = 0.2 + pulse * 0.4;
        if (u.glow) u.glow.material.opacity = 0.08 + pulse * 0.1;
      }
    }

    if (u.isStation && u.orbit) {
      var angle = u.orbit.angle + t * u.orbit.speed;
      m.position.set(
        Math.cos(angle) * u.orbit.dist,
        Math.sin(t * u.orbit.speed * 0.5) * 0.3,
        Math.sin(angle) * u.orbit.dist
      );
      m.rotation.y = t * 0.5;
      m.rotation.x = t * 0.3;
    }

    if (u.isMoon && u.orbit && u.parentPlanet) {
      var pa = u.orbit.parentAngle + t * u.orbit.parentSpeed;
      var px = Math.cos(pa) * u.orbit.parentDist;
      var pz = Math.sin(pa) * u.orbit.parentDist;
      var py = Math.sin(t * u.orbit.parentSpeed * 0.3) * 0.5;
      var ma = u.orbit.angle + t * u.orbit.speed;
      m.position.set(
        px + Math.cos(ma) * u.orbit.dist,
        py + Math.sin(ma * 2) * u.orbit.dist * 0.3,
        pz + Math.sin(ma) * u.orbit.dist
      );
    }
  }
}

function updateLabels() {
  for (var key in meshes) {
    var m = meshes[key];
    var u = m.userData;
    if (u.labelEl) {
      var pos = m.position.clone();
      pos.project(camera);
      if (pos.z < 1) {
        var x = (pos.x * 0.5 + 0.5) * window.innerWidth;
        var y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
        u.labelEl.style.left = x + 'px';
        u.labelEl.style.top = y + 'px';
        var dist = camera.position.distanceTo(m.position);
        if (u.isMoon && dist > 18) { u.labelEl.style.display = 'none'; }
        else if (dist > 45) { u.labelEl.style.display = 'none'; }
        else { u.labelEl.style.display = 'block'; }
      } else {
        u.labelEl.style.display = 'none';
      }
    }
    // Activity indicator
    if (u.activityEl) {
      if (agentActivity[u.id] && agentActivity[u.id].active) {
        var pos = m.position.clone();
        pos.y += u.orbit ? u.orbit.dist * 0.3 + 0.5 : 1;
        pos.project(camera);
        if (pos.z < 1) {
          var x = (pos.x * 0.5 + 0.5) * window.innerWidth;
          var y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
          u.activityEl.style.left = x + 'px';
          u.activityEl.style.top = y + 'px';
          u.activityEl.style.display = 'block';
          u.activityEl.textContent = agentActivity[u.id].text || 'working';
        } else {
          u.activityEl.style.display = 'none';
        }
      } else {
        u.activityEl.style.display = 'none';
      }
    }
  }
}

function updateAgentPanel() {
  var list = document.getElementById('agent-list');
  list.innerHTML = '';
  var sorted = Object.keys(agentActivity).sort();
  for (var i = 0; i < sorted.length; i++) {
    var aid = sorted[i];
    var a = agentActivity[aid];
    var row = document.createElement('div');
    row.className = 'agent-row';
    var dotClass = a.active ? 'active' : 'idle';
    row.innerHTML = '<span class="dot ' + dotClass + '"></span><span class="name">' + a.name + '</span><span class="status">' + a.status + '</span>';
    list.appendChild(row);
  }
}

function onClick(event) {
  var rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  var hits = raycaster.intersectObjects(scene.children.filter(function(c) {
    return c.isMesh && c.geometry && (c.geometry.type === 'SphereGeometry' || c.geometry.type === 'IcosahedronGeometry');
  }));
  if (hits.length > 0 && hits[0].object.userData.name) {
    var o = hits[0].object;
    document.getElementById('info-name').textContent = o.userData.name;
    var tag = document.getElementById('info-tag');
    tag.textContent = o.userData.label;
    var clr = o.userData.label === 'EVA' ? '#ffaa00' : (o.userData.label === 'Agent' ? '#00ff88' : (o.userData.label === 'SkillDomain' ? '#4488ff' : '#ff8844'));
    tag.style.background = clr + '22';
    tag.style.color = clr;
    var p = o.userData.props || {};
    var html = '';
    for (var k in p) { html += '<div><span class="k">' + k + '</span> ' + p[k] + '</div>'; }
    document.getElementById('info-props').innerHTML = html || 'Aucune propriete';
    // Show activity status
    var statusEl = document.getElementById('info-status');
    var statusText = document.getElementById('info-status-text');
    if (agentActivity[o.userData.id] && agentActivity[o.userData.id].active) {
      statusEl.style.display = 'flex';
      statusText.textContent = agentActivity[o.userData.id].text || 'Actif';
    } else {
      statusEl.style.display = 'none';
    }
    document.getElementById('info').classList.add('visible');
    if (selected) selected.material.emissiveIntensity = 0.2;
    selected = o;
    selected.material.emissiveIntensity = 0.6;
  } else {
    document.getElementById('info').classList.remove('visible');
    if (selected) { selected.material.emissiveIntensity = 0.2; selected = null; }
  }
}

function onResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
  requestAnimationFrame(animate);
  animTime += 0.008;
  controls.update();
  updatePositions(animTime);
  renderer.render(scene, camera);
  updateLabels();
}

function fetchAgentStatus() {
  fetch('/api/agents/status').then(function(r) { return r.json(); }).then(function(d) {
    // Update activity map
    var now = Date.now();
    for (var key in agentActivity) { agentActivity[key].active = false; }
    for (var i = 0; i < d.packets.length; i++) {
      var p = d.packets[i];
      var src = p.source || '';
      var ts = p.timestamp || '';
      // Agent is "active" if it published in the last 30 seconds
      if (src && (now - new Date(ts).getTime()) < 30000) {
        agentActivity[src] = {name: src, active: true, status: 'working', text: (p.payload && p.payload.mission ? p.payload.mission : 'working')};
      }
    }
    updateAgentPanel();
  }).catch(function(e) {});
}

function fetchPackets() {
  fetch('/api/packets').then(function(r) { return r.json(); }).then(function(d) {
    if (!d.packets || !d.packets.length) return;
    lastPackets = d.packets;
    var c = document.getElementById('packet-stream');
    c.innerHTML = '<h4><span class="live"></span>Flux temps reel</h4>';
    for (var i = 0; i < Math.min(d.packets.length, 8); i++) {
      var p = d.packets[i];
      var div = document.createElement('div');
      div.className = 'pkt';
      var t = (p.timestamp || '').slice(11, 19) || '--:--:--';
      var st = p.status || 'done';
      var stClr = st === 'done' ? '#00ff88' : (st === 'failed' ? '#ff4466' : '#ffaa44');
      div.innerHTML = '<span class="t">' + t + '</span><span class="s">' + p.source + '</span><span class="top">' + p.topic + '</span><span class="st" style="background:' + stClr + '22;color:' + stClr + '">' + st + '</span>';
      c.appendChild(div);
    }
  }).catch(function(e) {});
}

setInterval(function() { loadGraph(); }, 30000);
setInterval(fetchAgentStatus, 3000);
init();
setInterval(fetchPackets, 2000);
fetchPackets();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
