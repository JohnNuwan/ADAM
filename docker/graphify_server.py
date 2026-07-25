#!/usr/bin/env python3
"""Graphify V7 - Complete Dashboard: 3D Network Hub + Missions + Agent Thoughts + EVA Chat"""
from flask import Flask, jsonify, request
import psycopg2, json, os, urllib.request, time, threading
from datetime import datetime

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:***@postgres:5432/adam")
BUS_URL = os.environ.get("BUS_URL", "http://go-bus:8086")
VLLM_URL = os.environ.get("VLLM_URL", "http://192.168.1.5:8000")

nodes_cache = {"nodes": [], "edges": [], "ts": 0}
missions_queue = {"pending": [], "active": [], "done": []}
agent_thoughts = []
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

def poll_events():
    """Poll for new events to track agent activity"""
    while True:
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                pkts = data if isinstance(data, list) else data.get("events", [])
                with lock:
                    # Track thoughts from LLM interactions
                    for p in pkts:
                        src = p.get("source", "")
                        if src and "adam" in src.lower():
                            payload = p.get("payload", {})
                            if isinstance(payload, dict):
                                thought = payload.get("thought", payload.get("action", ""))
                                if thought and len(thought) > 5:
                                    agent_thoughts.append({
                                        "agent": src,
                                        "thought": thought,
                                        "timestamp": p.get("timestamp", ""),
                                        "topic": p.get("topic", "")
                                    })
                    # Keep last 50
                    if len(agent_thoughts) > 50:
                        agent_thoughts[:] = agent_thoughts[-50:]
        except Exception:
            pass
        time.sleep(5)

threading.Thread(target=refresh_graph, daemon=True).start()
threading.Thread(target=poll_events, daemon=True).start()

@app.route("/api/graph")
def get_graph():
    with lock:
        return jsonify(nodes_cache)

@app.route("/api/packets")
def get_packets():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            pkts = data if isinstance(data, list) else data.get("events", [])
            return jsonify({"packets": pkts})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

@app.route("/api/missions")
def get_missions():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:mission")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            missions = data if isinstance(data, list) else data.get("events", [])
            # Enrich with status
            for m in missions:
                m["status"] = m.get("payload", {}).get("status", "pending")
            return jsonify({"missions": missions})
    except Exception as e:
        return jsonify({"missions": [], "error": str(e)})

@app.route("/api/thoughts")
def get_thoughts():
    with lock:
        return jsonify({"thoughts": agent_thoughts[-20:]})

@app.route("/api/tools")
def get_tools():
    import os
    from pathlib import Path
    base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
    tools_data = {}
    adir = base / "agents"
    if adir.exists():
        for d in sorted(adir.iterdir()):
            if d.is_dir():
                name = "adam-" + d.name
                scripts = [f.name for f in sorted(d.glob("*.sh")) + sorted(d.glob("*.py"))]
                tools = []
                tdir = d / "tools"
                if tdir.exists():
                    tools = [f.name for f in sorted(tdir.iterdir()) if f.is_file()]
                if scripts or tools:
                    tools_data[name] = {"scripts": scripts[:15], "tools": tools[:15]}
    return jsonify({"tools": tools_data})

@app.route("/api/eva/chat", methods=["POST"])
def eva_chat():
    """Chat with EVA using Qwen LLM"""
    msg = request.json.get("message", "")
    if not msg:
        return jsonify({"error": "no message"})
    
    # Build context about current system state
    with lock:
        nodes = nodes_cache.get("nodes", [])
        agents = [n for n in nodes if n.get("label") == "Agent"]
        active_agents = len(agent_thoughts[-5:])
    
    system = f"""Tu es EVA, l'assistant orchestrateur du système ADAM.
Tu contrôles {len(agents)} agents autonomes qui tournent en local sur TheHive.
Tu peux: soumettre des objectifs, lancer des missions, vérifier l'état des agents, recommander des actions.
Réponds en français, de manière concise et utile."""

    payload = json.dumps({
        "model": "Qwen2.5-32B-Instruct-AWQ",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": msg}
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }).encode()
    
    try:
        req = urllib.request.Request(f"{VLLM_URL}/v1/chat/completions",
                                     data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            response = data["choices"][0]["message"]["content"]
            return jsonify({"response": response, "model": "Qwen2.5-32B"})
    except Exception as e:
        return jsonify({"response": f"Erreur LLM: {e}", "model": "error"})

@app.route("/api/eva/objective", methods=["POST"])
def submit_objective():
    """Submit an objective to EVA Mission Engine"""
    objective = request.json.get("objective", "")
    if not objective:
        return jsonify({"error": "no objective"})
    
    # Publish to Go Bus
    payload = json.dumps({"topic": "eva:objective", "source": "dashboard",
                          "payload": {"objective": objective}, "priority": 2}).encode()
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/publish", data=payload,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return jsonify({"status": "submitted", "objective": objective})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM Dashboard — EVA</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050510;color:#e0e8f0;font-family:'SF Pro Display','Segoe UI',system-ui,sans-serif;overflow:hidden}
#app{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:48px 1fr 1fr;width:100vw;height:100vh;gap:1px;background:rgba(68,102,136,0.1)}

/* Top Bar */
#topbar{grid-column:1/3;display:flex;align-items:center;justify-content:space-between;padding:0 20px;background:linear-gradient(180deg,rgba(5,5,16,0.98),rgba(5,5,16,0.9));backdrop-filter:blur(10px);z-index:100}
#topbar .logo{display:flex;align-items:center;gap:10px}
#topbar .logo .dot{width:8px;height:8px;border-radius:50%;background:#00aaff;box-shadow:0 0 12px #00aaff;animation:pulse 2s infinite}
#topbar .logo span{font-size:13px;font-weight:600;letter-spacing:0.5px}
#topbar .stats{display:flex;gap:20px;font-size:11px;color:#5577aa}
#topbar .stats .val{color:#e8e8f0;font-weight:600}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}

/* Panels */
.panel{background:rgba(5,5,16,0.92);overflow:hidden;display:flex;flex-direction:column;position:relative}
.panel h3{font-size:10px;color:#5577aa;text-transform:uppercase;letter-spacing:0.5px;padding:10px 14px;border-bottom:1px solid rgba(68,102,136,0.1);display:flex;align-items:center;gap:6px}
.panel h3 .live{width:5px;height:5px;border-radius:50%;background:#ff4466;animation:pulse 1s infinite}
.panel-content{flex:1;overflow-y:auto;padding:10px}
.panel-content::-webkit-scrollbar{width:3px}
.panel-content::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}

/* 3D Hub */
#hub3d{position:relative}
#hub3d canvas{display:block}

/* Agent Panel */
.agent-card{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #00ff88}
.agent-card.inactive{border-left-color:#446688}
.agent-card .name{font-size:12px;font-weight:600;color:#00ff88;margin-bottom:4px}
.agent-card .role{font-size:10px;color:#6688aa;margin-bottom:6px}
.agent-card .thought{font-size:10px;color:#88aacc;font-style:italic;line-height:1.4;padding:6px;background:rgba(68,102,136,0.08);border-radius:4px;margin-top:6px}
.agent-card .thought .time{font-size:9px;color:#446688;margin-right:6px}

/* Mission Panel */
.mission-card{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #00aaff}
.mission-card.running{border-left-color:#00ff88}
.mission-card.done{border-left-color:#446688}
.mission-card .objective{font-size:11px;font-weight:500;color:#e8e8f0;margin-bottom:4px}
.mission-card .agent{font-size:10px;color:#00aaff}
.mission-card .status{font-size:9px;padding:2px 8px;border-radius:8px;display:inline-block;margin-top:4px;font-weight:600}
.mission-card .status.pending{background:#ffaa4422;color:#ffaa44}
.mission-card .status.running{background:#00ff8822;color:#00ff88}
.mission-card .status.done{background:#44668822;color:#446688}

/* Chat Panel */
#chat-messages{display:flex;flex-direction:column;gap:8px;padding:10px}
.chat-msg{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;max-width:85%;font-size:11px;line-height:1.5}
.chat-msg.user{align-self:flex-end;background:rgba(0,170,255,0.15);border-left:3px solid #00aaff}
.chat-msg.eva{align-self:flex-start;background:rgba(0,255,136,0.08);border-left:3px solid #00ff88}
.chat-msg .time{font-size:9px;color:#446688;margin-bottom:4px}
#chat-input{display:flex;gap:8px;padding:10px;border-top:1px solid rgba(68,102,136,0.1)}
#chat-input input{flex:1;background:rgba(10,15,25,0.6);border:1px solid rgba(68,102,136,0.2);border-radius:6px;padding:8px 12px;color:#e8e8f0;font-size:11px;outline:none}
#chat-input input:focus{border-color:#00aaff}
#chat-input button{background:#00aaff;border:none;border-radius:6px;padding:8px 16px;color:#fff;font-size:11px;font-weight:600;cursor:pointer}
#chat-input button:hover{background:#0088cc}

/* Node labels */
.node-label{position:absolute;font-size:10px;font-weight:500;text-shadow:0 0 4px #000,0 0 8px #000;background:rgba(5,5,16,0.8);padding:2px 6px;border-radius:4px;pointer-events:none;white-space:nowrap;z-index:5;transform:translate(-50%,-50%)}

/* Responsive */
@media (max-width:1200px){
  #app{grid-template-columns:1fr;grid-template-rows:48px 300px 300px 300px 300px}
  #topbar{grid-column:1/2}
}
</style>
</head>
<body>
<div id="app">
  <div id="topbar">
    <div class="logo"><div class="dot"></div><span>ADAM Dashboard</span></div>
    <div class="stats" id="stats-bar"></div>
  </div>

  <!-- 3D Hub -->
  <div class="panel" id="hub3d">
    <h3>Network Flow Hub <span class="live"></span></h3>
    <div class="panel-content" id="hub-content">
      <canvas id="hub-canvas"></canvas>
    </div>
  </div>

  <!-- Agents Panel -->
  <div class="panel">
    <h3>Agents Actifs <span class="live"></span></h3>
    <div class="panel-content" id="agents-content">
      <div class="agent-card"><div class="name">Chargement...</div></div>
    </div>
  </div>

  <!-- Missions Panel -->
  <div class="panel">
    <h3>Missions <span class="live"></span></h3>
    <div class="panel-content" id="missions-content">
      <div class="mission-card"><div class="objective">Chargement...</div></div>
    </div>
  </div>

  <!-- EVA Chat Panel -->
  <div class="panel">
    <h3>EVA Chat <span class="live"></span></h3>
    <div class="panel-content" id="chat-content">
      <div id="chat-messages"></div>
    </div>
    <div id="chat-input">
      <input type="text" id="chat-msg" placeholder="Parle à EVA..." onkeypress="if(event.key==='Enter')sendChat()">
      <button onclick="sendChat()">Envoyer</button>
    </div>
  </div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var scene, camera, renderer, controls;
var nodes = {};
var flowParticles = [];
var animTime = 0;

function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050510);
  scene.fog = new THREE.FogExp2(0x050510, 0.008);

  var container = document.getElementById('hub-content');
  var w = container.clientWidth, h = container.clientHeight;
  camera = new THREE.PerspectiveCamera(55, w/h, 0.1, 500);
  camera.position.set(0, 12, 18);

  renderer = new THREE.WebGLRenderer({antialias: true, canvas: document.getElementById('hub-canvas')});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.3;
  controls.minDistance = 4;
  controls.maxDistance = 40;

  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();

  // Lights
  scene.add(new THREE.AmbientLight(0x222244));
  var dl = new THREE.DirectionalLight(0x4488ff, 0.8);
  dl.position.set(10, 20, 10);
  scene.add(dl);
  var dl2 = new THREE.DirectionalLight(0xff8844, 0.3);
  dl2.position.set(-10, -5, -10);
  scene.add(dl2);

  // Stars
  var sg = new THREE.BufferGeometry();
  var sp = new Float32Array(4000);
  for (var i = 0; i < 4000; i++) {
    var r = 50 + Math.random() * 200;
    var t = Math.random() * Math.PI * 2;
    var p = Math.acos(2 * Math.random() - 1);
    sp[i*3] = r * Math.sin(p) * Math.cos(t);
    sp[i*3+1] = r * Math.sin(p) * Math.sin(t);
    sp[i*3+2] = r * Math.cos(p);
  }
  sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({color: 0x445577, size: 0.3, transparent: true, opacity: 0.6, sizeAttenuation: true})));

  renderer.domElement.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);
  loadGraph();
  loadAll();
}

function loadGraph() {
  fetch('/api/graph').then(function(r) { return r.json(); }).then(function(data) {
    buildHub(data);
    animate();
  });
}

var NODE_COLORS = {
  'EVA':         {color: 0x00aaff, clr: '#00aaff', size: 1.2, emissive: 0x0066ff},
  'Agent':       {color: 0x00ff88, clr: '#00ff88', size: 0.45, emissive: 0x00cc55},
  'SkillDomain': {color: 0x4488ff, clr: '#4488ff', size: 0.15, emissive: 0x2244aa},
  'Service':     {color: 0xff8844, clr: '#ff8844', size: 0.35, emissive: 0xcc6622}
};

function buildHub(graphData) {
  // Clear old (keep lights and stars)
  while(scene.children.length > 5) scene.remove(scene.children[scene.children.length - 1]);

  var graphNodes = graphData.nodes;
  var graphEdges = graphData.edges;
  var nodePositions = {};

  // Separate by type
  var eva = [], agents = [], skills = [], services = [];
  for (var i = 0; i < graphNodes.length; i++) {
    var n = graphNodes[i];
    if (n.label === 'EVA') eva.push(n);
    else if (n.label === 'Agent') agents.push(n);
    else if (n.label === 'SkillDomain') skills.push(n);
    else if (n.label === 'Service') services.push(n);
  }

  // EVA center
  var evaNode = eva[0] || {id:'eva', name:'EVA', label:'EVA', properties:{}};
  nodePositions['eva'] = new THREE.Vector3(0, 0, 0);

  // Services inner ring
  var svcRadius = 2.5;
  for (var i = 0; i < services.length; i++) {
    var angle = (2 * Math.PI * i) / services.length;
    nodePositions[services[i].id] = new THREE.Vector3(Math.cos(angle) * svcRadius, Math.sin(angle) * svcRadius * 0.3, Math.sin(angle) * svcRadius);
  }

  // Agents main ring
  var agentRadius = 5.5;
  for (var i = 0; i < agents.length; i++) {
    var angle = (2 * Math.PI * i) / agents.length - Math.PI / 2;
    nodePositions[agents[i].id] = new THREE.Vector3(Math.cos(angle) * agentRadius, Math.sin(angle * 2) * 0.8, Math.sin(angle) * agentRadius);
  }

  // Skills via Fibonacci around parent agents
  var skillParents = {};
  for (var i = 0; i < graphEdges.length; i++) {
    var e = graphEdges[i];
    if (e.relation === 'has_skill') { skillParents[e.target] = e.source; }
  }
  var skillCount = {};
  for (var sid in skillParents) { var pid = skillParents[sid]; if (!skillCount[pid]) skillCount[pid] = 0; skillCount[pid]++; }
  var skillIdx = {};
  for (var sid in skillParents) {
    var pid = skillParents[sid];
    if (!skillIdx[pid]) skillIdx[pid] = 0;
    var basePos = nodePositions[pid] || new THREE.Vector3(Math.random()*3, 0, Math.random()*3);
    var total = skillCount[pid] || 10;
    var idx = skillIdx[pid]++;
    var ga = Math.PI * (3 - Math.sqrt(5));
    var y = 1 - (idx / (total - 1 || 1)) * 2;
    var rad = Math.sqrt(1 - y * y);
    var theta = ga * idx;
    var dist = 0.7 + (y * 0.3 + 0.5) * 0.4;
    nodePositions[sid] = new THREE.Vector3(basePos.x + Math.cos(theta) * rad * dist, basePos.y + y * dist * 0.5, basePos.z + Math.sin(theta) * rad * dist);
  }

  // Build nodes
  nodes = {};
  for (var i = 0; i < graphNodes.length; i++) {
    var n = graphNodes[i];
    var pos = nodePositions[n.id] || new THREE.Vector3(Math.random()*5-2.5, Math.random()*5-2.5, Math.random()*5-2.5);
    var cfg = NODE_COLORS[n.label] || NODE_COLORS['SkillDomain'];
    var size = cfg.size;
    var geom = new THREE.SphereGeometry(size, n.label === 'EVA' ? 48 : 20, n.label === 'EVA' ? 48 : 20);
    var mat = new THREE.MeshPhongMaterial({color: cfg.color, emissive: cfg.emissive || cfg.color, emissiveIntensity: n.label === 'EVA' ? 0.6 : (n.label === 'Agent' ? 0.25 : 0.15), shininess: 60});
    var mesh = new THREE.Mesh(geom, mat);
    mesh.position.copy(pos);
    mesh.userData = {id: n.id, name: n.name, label: n.label, props: n.properties};
    scene.add(mesh);
    nodes[n.id] = mesh;

    // Glow for EVA
    if (n.label === 'EVA') {
      for (var ci = 0; ci < 3; ci++) {
        var glow = new THREE.Mesh(new THREE.SphereGeometry(size * (1.2 + ci * 0.25), 32, 32), new THREE.MeshBasicMaterial({color: 0x00aaff, transparent: true, opacity: 0.06 - ci * 0.015, side: THREE.BackSide}));
        glow.position.copy(pos);
        scene.add(glow);
      }
    }

    // Label
    var l = document.createElement('div');
    l.className = 'node-label';
    l.textContent = n.label === 'SkillDomain' ? n.name.substring(0, 10) : n.name;
    l.style.color = cfg.clr;
    l.style.fontSize = n.label === 'EVA' ? '14px' : (n.label === 'Agent' ? '10px' : (n.label === 'Service' ? '9px' : '7px'));
    l.style.fontWeight = n.label === 'EVA' ? '700' : '500';
    document.body.appendChild(l);
    mesh.userData.labelEl = l;
  }

  // Edges
  for (var i = 0; i < graphEdges.length; i++) {
    var e = graphEdges[i];
    if (nodes[e.source] && nodes[e.target]) {
      var s = nodes[e.source].position;
      var t = nodes[e.target].position;
      var dist = s.distanceTo(t);
      if (dist < 15) {
        var mid = new THREE.Vector3().addVectors(s, t).multiplyScalar(0.5);
        var curve = new THREE.QuadraticBezierCurve3(s, mid, t);
        var pts = curve.getPoints(20);
        var opacity = Math.min(0.2, 0.4 - dist * 0.02);
        scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({color: 0x446688, transparent: true, opacity: opacity})));
      }
    }
  }

  // Hub rings
  var hubRing = new THREE.Line(new THREE.BufferGeometry().setFromPoints(function() {
    var pts = [];
    for (var i = 0; i < 64; i++) { var a = (i / 64) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * 2.2, Math.sin(a) * 2.2 * 0.3, Math.sin(a) * 2.2)); }
    return pts;
  }()), new THREE.LineBasicMaterial({color: 0x334466, transparent: true, opacity: 0.08}));
  scene.add(hubRing);

  // Stats
  document.getElementById('stats-bar').innerHTML = '<div>Agents: <span class="val">' + agents.length + '</span></div><div>Skills: <span class="val">' + skills.length + '</span></div><div>Services: <span class="val">' + services.length + '</span></div>';
}

function updateLabels() {
  for (var key in nodes) {
    var mesh = nodes[key];
    if (mesh.userData.labelEl) {
      var pos = mesh.position.clone();
      pos.project(camera);
      if (pos.z < 1) {
        mesh.userData.labelEl.style.left = ((pos.x * 0.5 + 0.5) * renderer.domElement.clientWidth) + 'px';
        mesh.userData.labelEl.style.top = ((-pos.y * 0.5 + 0.5) * renderer.domElement.clientHeight) + 'px';
        var dist = camera.position.distanceTo(mesh.position);
        if (mesh.userData.label === 'SkillDomain' && dist > 20) { mesh.userData.labelEl.style.display = 'none'; }
        else if (dist > 35) { mesh.userData.labelEl.style.display = 'none'; }
        else { mesh.userData.labelEl.style.display = 'block'; }
      } else { mesh.userData.labelEl.style.display = 'none'; }
    }
  }
}

function onClick(event) {
  var rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  var hits = raycaster.intersectObjects(scene.children.filter(function(c) { return c.isMesh && c.userData.name; }));
  if (hits.length > 0 && hits[0].object.userData.name) {
    var o = hits[0].object;
    var info = document.getElementById('info-name');
    if (info) info.textContent = o.userData.name;
    var tag = document.getElementById('info-tag');
    if (tag) tag.textContent = o.userData.label;
    var props = document.getElementById('info-props');
    if (props) {
      var html = '';
      for (var k in (o.userData.props || {})) { html += '<div><span class="k">' + k + '</span> ' + o.userData.props[k] + '</div>'; }
      props.innerHTML = html || 'Aucune propriete';
    }
    var panel = document.getElementById('info-panel');
    if (panel) panel.classList.add('visible');
    if (selected) selected.material.emissiveIntensity = 0.2;
    selected = o;
    selected.material.emissiveIntensity = 0.8;
  } else {
    var panel = document.getElementById('info-panel');
    if (panel) panel.classList.remove('visible');
    if (selected) { selected.material.emissiveIntensity = 0.2; selected = null; }
  }
}

function onResize() {
  var container = document.getElementById('hub-content');
  if (!container) return;
  var w = container.clientWidth, h = container.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

function animate() {
  requestAnimationFrame(animate);
  animTime += 0.02;
  controls.update();
  updateLabels();
  renderer.render(scene, camera);
}

function loadAll() {
  fetchAgents();
  fetchMissions();
  fetchPackets();
  setInterval(fetchAgents, 5000);
  setInterval(fetchMissions, 5000);
  setInterval(fetchPackets, 3000);
}

function fetchAgents() {
  fetch('/api/thoughts').then(function(r) { return r.json(); }).then(function(d) {
    var container = document.getElementById('agents-content');
    container.innerHTML = '';
    var thoughts = d.thoughts || [];
    var byAgent = {};
    for (var i = 0; i < thoughts.length; i++) {
      var t = thoughts[i];
      if (!byAgent[t.agent]) byAgent[t.agent] = [];
      byAgent[t.agent].push(t);
    }
    for (var agent in byAgent) {
      var card = document.createElement('div');
      card.className = 'agent-card';
      var last = byAgent[agent][byAgent[agent].length - 1];
      card.innerHTML = '<div class="name">' + agent + '</div><div class="role">Dernière activité</div>' +
                       '<div class="thought"><span class="time">' + (last.timestamp || '').slice(11, 19) + '</span>' + (last.thought || '').substring(0, 80) + '</div>';
      container.appendChild(card);
    }
    if (Object.keys(byAgent).length === 0) {
      container.innerHTML = '<div class="agent-card inactive"><div class="name">Aucun agent actif</div></div>';
    }
  }).catch(function(e) {});
}

function fetchMissions() {
  fetch('/api/missions').then(function(r) { return r.json(); }).then(function(d) {
    var container = document.getElementById('missions-content');
    container.innerHTML = '';
    var missions = d.missions || [];
    for (var i = 0; i < Math.min(missions.length, 10); i++) {
      var m = missions[i];
      var card = document.createElement('div');
      card.className = 'mission-card ' + (m.status || 'pending');
      var payload = m.payload || {};
      card.innerHTML = '<div class="objective">' + (payload.mission || payload.objective || m.topic).substring(0, 60) + '</div>' +
                       '<div class="agent">' + m.source + '</div>' +
                       '<div class="status ' + (m.status || 'pending') + '">' + (m.status || 'pending') + '</div>';
      container.appendChild(card);
    }
    if (missions.length === 0) {
      container.innerHTML = '<div class="mission-card"><div class="objective">Aucune mission</div></div>';
    }
  }).catch(function(e) {});
}

function fetchPackets() {
  fetch('/api/packets').then(function(r) { return r.json(); }).then(function(d) {
    var c = document.getElementById('packet-stream');
    if (!c) return;
    var packets = d.packets || [];
    c.innerHTML = '<h4><span class="live"></span>Flux temps reel</h4>';
    for (var i = 0; i < Math.min(packets.length, 8); i++) {
      var p = packets[i];
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

function sendChat() {
  var input = document.getElementById('chat-msg');
  var msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  
  // Add user message
  var container = document.getElementById('chat-messages');
  var userDiv = document.createElement('div');
  userDiv.className = 'chat-msg user';
  userDiv.innerHTML = '<div class="time">' + new Date().toLocaleTimeString() + '</div>' + msg;
  container.appendChild(userDiv);
  container.scrollTop = container.scrollHeight;
  
  // Send to EVA
  fetch('/api/eva/chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({message: msg})
  }).then(function(r) { return r.json(); }).then(function(d) {
    var evaDiv = document.createElement('div');
    evaDiv.className = 'chat-msg eva';
    evaDiv.innerHTML = '<div class="time">EVA (' + (d.model || 'Qwen') + ')</div>' + (d.response || 'Pas de réponse');
    container.appendChild(evaDiv);
    container.scrollTop = container.scrollHeight;
  }).catch(function(e) {
    var errDiv = document.createElement('div');
    errDiv.className = 'chat-msg eva';
    errDiv.innerHTML = '<div class="time">Erreur</div>Impossible de joindre EVA: ' + e;
    container.appendChild(errDiv);
    container.scrollTop = container.scrollHeight;
  });
}

function submitObjective(obj) {
  fetch('/api/eva/objective', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({objective: obj})
  }).then(function(r) { return r.json(); }).then(function(d) {
    addChatMessage('Objectif soumis: ' + obj);
  });
}

function addChatMessage(text) {
  var container = document.getElementById('chat-messages');
  var div = document.createElement('div');
  div.className = 'chat-msg eva';
  div.innerHTML = '<div class="time">Système</div>' + text;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

// Start
init();
setInterval(loadGraph, 30000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
