#!/usr/bin/env python3
"""Graphify V8 — Clean Hub + Panel System (draggable/collapsible)"""
from flask import Flask, jsonify, request
import psycopg2, json, os, urllib.request, time, threading
from collections import defaultdict

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:***@postgres:5432/adam")
BUS_URL = "http://go-bus:8086"
VLLM_URL = os.environ.get("VLLM_URL", "http://192.168.1.5:8000")

# ─── Data Model ───
# Hub: {eva: {...}, agents: [...], skills: [...], services: [...], edges: [...]}
# Activity: {agent_name: {last_thought, timestamp, topic}}
# Missions: [{agent, mission, status, objective, timestamp}]
# Tools: {agent_name: {scripts: [...], tools: [...]}}

graph_cache = {"hub": None, "ts": 0}
activity_cache = {}
missions_cache = []
tools_cache = {}
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

            # Build clean hub model
            hub = {"eva": None, "agents": [], "skills": [], "services": [], "edges": edges}
            for n in nodes:
                if n["label"] == "EVA":
                    hub["eva"] = n
                elif n["label"] == "Agent":
                    hub["agents"].append(n)
                elif n["label"] == "SkillDomain":
                    hub["skills"].append(n)
                elif n["label"] == "Service":
                    hub["services"].append(n)

            with lock:
                graph_cache["hub"] = hub
                graph_cache["ts"] = time.time()
        except Exception as e:
            print(f"[ERR] {e}", flush=True)
        time.sleep(15)

def poll_activity():
    while True:
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=30&topic=adam:packet")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                pkts = data if isinstance(data, list) else data.get("events", [])
                with lock:
                    for p in pkts:
                        src = p.get("source", "")
                        if src and "adam" in src.lower():
                            payload = p.get("payload", {})
                            thought = payload.get("thought", payload.get("action", payload.get("status", ""))) if isinstance(payload, dict) else ""
                            if thought:
                                activity_cache[src] = {
                                    "thought": str(thought)[:150],
                                    "timestamp": p.get("timestamp", ""),
                                    "topic": p.get("topic", "")
                                }
                    # Keep last 30
                    if len(activity_cache) > 30:
                        keys = sorted(activity_cache.keys(), key=lambda k: activity_cache[k]["timestamp"], reverse=True)
                        for k in keys[30:]:
                            del activity_cache[k]
        except Exception:
            pass
        time.sleep(4)

def poll_missions():
    while True:
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:mission")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                missions = data if isinstance(data, list) else data.get("events", [])
                with lock:
                    missions_cache.clear()
                    for m in missions:
                        missions_cache.append(m)
        except Exception:
            pass
        time.sleep(5)

def refresh_tools():
    while True:
        try:
            import os
            from pathlib import Path
            base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
            adir = base / "agents"
            new_tools = {}
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
                            new_tools[name] = {"scripts": scripts[:15], "tools": tools[:15]}
            with lock:
                tools_cache.clear()
                tools_cache.update(new_tools)
        except Exception:
            pass
        time.sleep(60)

threading.Thread(target=refresh_graph, daemon=True).start()
threading.Thread(target=poll_activity, daemon=True).start()
threading.Thread(target=poll_missions, daemon=True).start()
threading.Thread(target=refresh_tools, daemon=True).start()

@app.route("/api/graph")
def api_graph():
    with lock:
        return jsonify(graph_cache)

@app.route("/api/activity")
def api_activity():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            pkts = data if isinstance(data, list) else data.get("events", [])
            activity = {}
            for p in pkts:
                src = p.get("source", "")
                if src:
                    payload = p.get("payload", {})
                    thought = payload.get("action", payload.get("status", "")) if isinstance(payload, dict) else ""
                    activity[src] = {
                        "thought": str(thought)[:150],
                        "timestamp": p.get("timestamp", ""),
                        "topic": p.get("topic", "")
                    }
            return jsonify({"activity": activity})
    except Exception as e:
        return jsonify({"activity": {}, "error": str(e)})

@app.route("/api/missions")
def api_missions():
    with lock:
        return jsonify({"missions": missions_cache})

@app.route("/api/tools")
def api_tools():
    with lock:
        return jsonify({"tools": tools_cache})

@app.route("/api/packets")
def api_packets():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=15&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            pkts = data if isinstance(data, list) else data.get("events", [])
            return jsonify({"packets": pkts})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

@app.route("/api/eva/chat", methods=["POST"])
def eva_chat():
    msg = request.json.get("message", "")
    if not msg:
        return jsonify({"error": "no message"})
    with lock:
        agents = graph_cache.get("hub", {}).get("agents", []) if graph_cache.get("hub") else []
    system = f"""Tu es EVA, l'assistant orchestrateur du système ADAM. Tu contrôles {len(agents)} agents autonomes sur TheHive. Réponds en français, concis et utile."""
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
        req = urllib.request.Request(f"{VLLM_URL}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return jsonify({"response": data["choices"][0]["message"]["content"], "model": "Qwen2.5-32B"})
    except Exception as e:
        return jsonify({"response": f"Erreur LLM: {e}", "model": "error"})

@app.route("/api/eva/objective", methods=["POST"])
def submit_objective():
    objective = request.json.get("objective", "")
    if not objective:
        return jsonify({"error": "no objective"})
    payload = json.dumps({"topic": "eva:objective", "source": "dashboard", "payload": {"objective": objective}, "priority": 2}).encode()
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/publish", data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
        return jsonify({"status": "submitted", "objective": objective})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM — EVA Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050510;color:#e0e8f0;font-family:'SF Pro Display','Segoe UI',system-ui,sans-serif;overflow:hidden}

/* Top bar */
#topbar{position:fixed;top:0;left:0;right:0;height:44px;background:linear-gradient(180deg,rgba(5,5,16,0.98),rgba(5,5,16,0.9));display:flex;align-items:center;justify-content:space-between;padding:0 20px;z-index:1000;backdrop-filter:blur(10px);border-bottom:1px solid rgba(68,102,136,0.1)}
#topbar .logo{display:flex;align-items:center;gap:10px}
#topbar .logo .dot{width:8px;height:8px;border-radius:50%;background:#00aaff;box-shadow:0 0 12px #00aaff;animation:pulse 2s infinite}
#topbar .logo span{font-size:13px;font-weight:600;letter-spacing:0.5px}
#topbar .stats{display:flex;gap:20px;font-size:11px;color:#5577aa}
#topbar .stats .val{color:#e8e8f0;font-weight:600}
#topbar .nav{display:flex;gap:8px}
#topbar .nav button{background:rgba(68,102,136,0.1);border:1px solid rgba(68,102,136,0.2);border-radius:6px;padding:5px 12px;color:#88aacc;font-size:11px;cursor:pointer;transition:all 0.2s}
#topbar .nav button:hover{background:rgba(0,170,255,0.15);color:#00aaff}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}

/* Main area */
#workspace{position:fixed;top:44px;left:0;right:0;bottom:0;display:flex}
#canvas-area{flex:1;position:relative;background:#050510}
#canvas-area canvas{display:block}

/* Panels */
.panel{position:absolute;background:rgba(5,5,16,0.94);border:1px solid rgba(68,102,136,0.2);border-radius:12px;display:flex;flex-direction:column;min-width:280px;max-width:400px;box-shadow:0 8px 32px rgba(0,0,0,0.4);backdrop-filter:blur(10px);z-index:100}
.panel-header{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid rgba(68,102,136,0.1);cursor:move;user-select:none}
.panel-header h3{font-size:10px;color:#5577aa;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:6px}
.panel-header .live{width:5px;height:5px;border-radius:50%;background:#ff4466;animation:pulse 1s infinite}
.panel-header .controls{display:flex;gap:4px}
.panel-header .controls button{background:none;border:none;color:#446688;font-size:12px;cursor:pointer;padding:2px 6px;border-radius:4px}
.panel-header .controls button:hover{color:#e8e8f0;background:rgba(68,102,136,0.1)}
.panel-content{flex:1;overflow-y:auto;padding:10px;min-height:100px;max-height:400px}
.panel-content::-webkit-scrollbar{width:3px}
.panel-content::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}
.panel.collapsed .panel-content{display:none}
.panel.collapsed{max-height:44px}
.panel.minimized{max-height:44px;min-height:44px;overflow:hidden}
.panel.minimized .panel-content{display:none}
.panel.minimized .panel-header{cursor:pointer}

/* Panel positions (default) */
#panel-agents{top:20px;left:20px;width:300px}
#panel-missions{bottom:20px;left:20px;width:340px;max-height:300px}
#panel-chat{bottom:20px;right:20px;width:380px;max-height:400px}
#panel-flow{top:20px;right:20px;width:340px;max-height:350px}

/* Cards */
.card{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #00ff88;transition:transform 0.2s}
.card:hover{transform:translateX(2px)}
.card.inactive{border-left-color:#446688}
.card .name{font-size:12px;font-weight:600;color:#00ff88;margin-bottom:4px}
.card .role{font-size:10px;color:#6688aa;margin-bottom:4px}
.card .thought{font-size:10px;color:#88aacc;font-style:italic;line-height:1.4;padding:6px;background:rgba(68,102,136,0.08);border-radius:4px;margin-top:6px}
.card .thought .time{font-size:9px;color:#446688;margin-right:6px}
.card .tools-list{font-size:9px;color:#5577aa;margin-top:6px;padding-top:6px;border-top:1px solid rgba(68,102,136,0.1)}
.card .tools-list .t{color:#00ff88;font-family:monospace}

/* Mission cards */
.mission-card{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #00aaff}
.mission-card.running{border-left-color:#00ff88}
.mission-card.done{border-left-color:#446688}
.mission-card .objective{font-size:11px;font-weight:500;color:#e8e8f0;margin-bottom:4px}
.mission-card .agent{font-size:10px;color:#00aaff}
.mission-card .status{font-size:9px;padding:2px 8px;border-radius:8px;display:inline-block;margin-top:4px;font-weight:600}
.mission-card .status.pending{background:#ffaa4422;color:#ffaa44}
.mission-card .status.running{background:#00ff8822;color:#00ff88}
.mission-card .status.done{background:#44668822;color:#446688}

/* Chat */
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

/* Flow packets */
.flow-row{display:flex;align-items:center;gap:5px;padding:4px 0;border-bottom:1px solid rgba(68,102,136,0.06);font-size:10px;font-family:'SF Mono',Menlo,monospace;color:#88aacc}
.flow-row .t{color:#446688;min-width:55px}
.flow-row .s{color:#00ff88;font-weight:600;min-width:65px}
.flow-row .top{color:#aaccff;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.flow-row .st{font-size:8px;padding:1px 4px;border-radius:3px;font-weight:600;text-transform:uppercase}

/* Node labels */
.node-label{position:absolute;font-size:10px;font-weight:500;text-shadow:0 0 4px #000,0 0 8px #000;background:rgba(5,5,16,0.8);padding:2px 6px;border-radius:4px;pointer-events:none;white-space:nowrap;z-index:5;transform:translate(-50%,-50%)}

/* Info panel (node click) */
#info-panel{position:fixed;z-index:500;background:rgba(5,5,16,0.95);padding:14px 18px;border-radius:12px;border:1px solid rgba(68,102,136,0.25);max-width:280px;pointer-events:none;opacity:0;transition:all 0.3s;transform:translateY(-5px)}
#info-panel.visible{opacity:1;transform:translateY(0)}
#info-panel h3{margin:0 0 2px;font-size:15px;font-weight:600}
#info-panel .tag{display:inline-block;font-size:9px;padding:2px 8px;border-radius:10px;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600}
#info-panel .props{font-size:11px;line-height:1.6;color:#88aacc}
#info-panel .props .k{color:#5577aa;font-size:10px}
#info-panel .tools{margin-top:8px;padding-top:8px;border-top:1px solid rgba(68,102,136,0.15);font-size:10px;color:#5577aa}
#info-panel .tools .t{color:#00ff88;font-family:monospace}
</style>
</head>
<body>
<div id="topbar">
  <div class="logo"><div class="dot"></div><span>ADAM Dashboard</span></div>
  <div class="stats" id="stats-bar"></div>
  <div class="nav">
    <button onclick="togglePanel('panel-agents')">Agents</button>
    <button onclick="togglePanel('panel-missions')">Missions</button>
    <button onclick="togglePanel('panel-chat')">EVA Chat</button>
    <button onclick="togglePanel('panel-flow')">Flux</button>
  </div>
</div>

<div id="workspace">
  <div id="canvas-area">
    <canvas id="hub-canvas"></canvas>
  </div>

  <!-- Agents Panel -->
  <div class="panel" id="panel-agents">
    <div class="panel-header" onmousedown="dragStart(event,'panel-agents')">
      <h3>Agents <span class="live"></span></h3>
      <div class="controls">
        <button onclick="minimizePanel('panel-agents')">_</button>
        <button onclick="togglePanel('panel-agents')">×</button>
      </div>
    </div>
    <div class="panel-content" id="agents-content"></div>
  </div>

  <!-- Missions Panel -->
  <div class="panel" id="panel-missions">
    <div class="panel-header" onmousedown="dragStart(event,'panel-missions')">
      <h3>Missions <span class="live"></span></h3>
      <div class="controls">
        <button onclick="minimizePanel('panel-missions')">_</button>
        <button onclick="togglePanel('panel-missions')">×</button>
      </div>
    </div>
    <div class="panel-content" id="missions-content"></div>
  </div>

  <!-- EVA Chat Panel -->
  <div class="panel" id="panel-chat">
    <div class="panel-header" onmousedown="dragStart(event,'panel-chat')">
      <h3>EVA Chat <span class="live"></span></h3>
      <div class="controls">
        <button onclick="minimizePanel('panel-chat')">_</button>
        <button onclick="togglePanel('panel-chat')">×</button>
      </div>
    </div>
    <div class="panel-content">
      <div id="chat-messages"></div>
    </div>
    <div id="chat-input">
      <input type="text" id="chat-msg" placeholder="Parle à EVA..." onkeypress="if(event.key==='Enter')sendChat()">
      <button onclick="sendChat()">Envoyer</button>
    </div>
  </div>

  <!-- Flow Panel -->
  <div class="panel" id="panel-flow">
    <div class="panel-header" onmousedown="dragStart(event,'panel-flow')">
      <h3>Flux temps réel <span class="live"></span></h3>
      <div class="controls">
        <button onclick="minimizePanel('panel-flow')">_</button>
        <button onclick="togglePanel('panel-flow')">×</button>
      </div>
    </div>
    <div class="panel-content" id="flow-content"></div>
  </div>
</div>

<!-- Info panel -->
<div id="info-panel">
  <h3 id="info-name">-</h3>
  <div class="tag" id="info-tag"></div>
  <div class="props" id="info-props"></div>
  <div class="tools" id="info-tools" style="display:none"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
// ─── Panel System ───
var dragState = {};

function togglePanel(id) {
  var p = document.getElementById(id);
  p.classList.toggle('collapsed');
}

function minimizePanel(id) {
  var p = document.getElementById(id);
  p.classList.toggle('minimized');
}

function dragStart(e, id) {
  if (e.target.tagName === 'BUTTON') return;
  dragState = {id: id, offsetX: e.clientX - document.getElementById(id).offsetLeft,
               offsetY: e.clientY - document.getElementById(id).offsetTop};
  document.addEventListener('mousemove', dragMove);
  document.addEventListener('mouseup', dragEnd);
}

function dragMove(e) {
  var p = document.getElementById(dragState.id);
  p.style.left = (e.clientX - dragState.offsetX) + 'px';
  p.style.top = (e.clientY - dragState.offsetY) + 'px';
  p.style.bottom = 'auto';
  p.style.right = 'auto';
}

function dragEnd() {
  document.removeEventListener('mousemove', dragMove);
  document.removeEventListener('mouseup', dragEnd);
}

// ─── 3D Hub ───
var scene, camera, renderer, controls;
var nodes = {};
var selected = null;

function init() {
  var container = document.getElementById('canvas-area');
  var w = container.clientWidth, h = container.clientHeight;

  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050510);
  scene.fog = new THREE.FogExp2(0x050510, 0.008);

  camera = new THREE.PerspectiveCamera(55, w/h, 0.1, 500);
  camera.position.set(0, 12, 18);

  renderer = new THREE.WebGLRenderer({antialias: true, canvas: document.getElementById('hub-canvas')});
  renderer.setSize(w, h);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.25;
  controls.minDistance = 4;
  controls.maxDistance = 40;

  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();

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

function buildHub(data) {
  var hub = data.hub;
  if (!hub) return;

  // Clear old
  while(scene.children.length > 5) scene.remove(scene.children[scene.children.length - 1]);
  nodes = {};

  var edges = data.edges || [];
  var nodePositions = {};

  // EVA
  if (hub.eva) {
    nodePositions['eva'] = new THREE.Vector3(0, 0, 0);
  }

  // Services inner ring
  var svcRadius = 2.5;
  for (var i = 0; i < hub.services.length; i++) {
    var angle = (2 * Math.PI * i) / hub.services.length;
    nodePositions[hub.services[i].id] = new THREE.Vector3(Math.cos(angle) * svcRadius, Math.sin(angle) * svcRadius * 0.3, Math.sin(angle) * svcRadius);
  }

  // Agents main ring
  var agentRadius = 5.5;
  for (var i = 0; i < hub.agents.length; i++) {
    var angle = (2 * Math.PI * i) / hub.agents.length - Math.PI / 2;
    nodePositions[hub.agents[i].id] = new THREE.Vector3(Math.cos(angle) * agentRadius, Math.sin(angle * 2) * 0.8, Math.sin(angle) * agentRadius);
  }

  // Skills via Fibonacci around parent agents
  var skillParents = {};
  for (var i = 0; i < edges.length; i++) {
    var e = edges[i];
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

  // Remove all old labels
  document.querySelectorAll('.node-label').forEach(function(el) { el.remove(); });

  // Build nodes
  var allNodes = [hub.eva].concat(hub.agents).concat(hub.services).concat(hub.skills);
  for (var i = 0; i < allNodes.length; i++) {
    var n = allNodes[i];
    if (!n) continue;
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

    if (n.label === 'EVA') {
      for (var ci = 0; ci < 3; ci++) {
        var glow = new THREE.Mesh(new THREE.SphereGeometry(size * (1.2 + ci * 0.25), 32, 32), new THREE.MeshBasicMaterial({color: 0x00aaff, transparent: true, opacity: 0.06 - ci * 0.015, side: THREE.BackSide}));
        glow.position.copy(pos);
        scene.add(glow);
      }
    }

    // Remove old label if exists (prevent duplication)
    if (mesh.userData.labelEl) {
      mesh.userData.labelEl.remove();
    }
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
  for (var i = 0; i < edges.length; i++) {
    var e = edges[i];
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

  var agentRing = new THREE.Line(new THREE.BufferGeometry().setFromPoints(function() {
    var pts = [];
    for (var i = 0; i < 64; i++) { var a = (i / 64) * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * 5.0, 0, Math.sin(a) * 5.0)); }
    return pts;
  }()), new THREE.LineBasicMaterial({color: 0x334466, transparent: true, opacity: 0.06}));
  scene.add(agentRing);

  // Stats
  document.getElementById('stats-bar').innerHTML = '<div>Agents: <span class="val">' + hub.agents.length + '</span></div><div>Skills: <span class="val">' + hub.skills.length + '</span></div><div>Services: <span class="val">' + hub.services.length + '</span></div>';
}

function updateLabels() {
  for (var key in nodes) {
    var mesh = nodes[key];
    if (mesh.userData.labelEl) {
      var pos = mesh.position.clone();
      pos.project(camera);
      if (pos.z < 1) {
        var w = renderer.domElement.clientWidth;
        var h = renderer.domElement.clientHeight;
        mesh.userData.labelEl.style.left = ((pos.x * 0.5 + 0.5) * w) + 'px';
        mesh.userData.labelEl.style.top = ((-pos.y * 0.5 + 0.5) * h) + 'px';
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
    document.getElementById('info-name').textContent = o.userData.name;
    var tag = document.getElementById('info-tag');
    tag.textContent = o.userData.label;
    var cfg = NODE_COLORS[o.userData.label] || NODE_COLORS['SkillDomain'];
    tag.style.background = cfg.clr + '22';
    tag.style.color = cfg.clr;
    var p = o.userData.props || {};
    var html = '';
    for (var k in p) { html += '<div><span class="k">' + k + '</span> ' + p[k] + '</div>'; }
    document.getElementById('info-props').innerHTML = html || 'Aucune propriete';
    // Show tools if agent
    var toolsEl = document.getElementById('info-tools');
    if (o.userData.label === 'Agent') {
      toolsEl.style.display = 'block';
      fetch('/api/tools').then(function(r){return r.json()}).then(function(td){
        var data = td.tools || {};
        var agentName = o.userData.name.toLowerCase().replace(/^adam-/,'');
        var key = null;
        for (var k in data) {
          if (k.toLowerCase().includes(agentName) || agentName.includes(k.toLowerCase().replace('adam-',''))) { key = k; break; }
        }
        if (!key) key = 'adam-' + agentName;
        var tools = data[key] || {scripts:[],tools:[]};
        var tHtml = '<div style="margin-bottom:4px;color:#88aacc">Scripts:</div>';
        for (var si=0;si<Math.min(tools.scripts.length,8);si++) {
          tHtml += '<div class="t">  ' + tools.scripts[si] + '</div>';
        }
        if (tools.tools.length) {
          tHtml += '<div style="margin-top:4px;margin-bottom:4px;color:#88aacc">Outils:</div>';
          for (var ti=0;ti<Math.min(tools.tools.length,8);ti++) {
            tHtml += '<div class="t">  ' + tools.tools[ti] + '</div>';
          }
        }
        toolsEl.innerHTML = tHtml || 'Aucun outil';
      });
    } else { toolsEl.style.display = 'none'; }
    document.getElementById('info-panel').classList.add('visible');
    if (selected) selected.material.emissiveIntensity = 0.2;
    selected = o;
    selected.material.emissiveIntensity = 0.8;
  } else {
    document.getElementById('info-panel').classList.remove('visible');
    if (selected) { selected.material.emissiveIntensity = 0.2; selected = null; }
  }
}

function onResize() {
  var container = document.getElementById('canvas-area');
  if (!container) return;
  var w = container.clientWidth, h = container.clientHeight;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  updateLabels();

  // Animate flow particles
  for (var i = flowParticles.length - 1; i >= 0; i--) {
    var p = flowParticles[i];
    p.progress += p.speed;
    if (p.progress > 1) {
      // Respawn
      var agentKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'Agent'; });
      var svcKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'Service'; });
      var allKeys = agentKeys.concat(svcKeys);
      if (allKeys.length > 1) {
        var src = allKeys[Math.floor(Math.random() * allKeys.length)];
        var dst = allKeys[Math.floor(Math.random() * allKeys.length)];
        if (src !== dst && nodes[src] && nodes[dst]) {
          p.curve = new THREE.QuadraticBezierCurve3(nodes[src].position, new THREE.Vector3().addVectors(nodes[src].position, nodes[dst].position).multiplyScalar(0.5), nodes[dst].position);
          p.progress = 0;
        }
      }
    }
    var pt = p.curve.getPoint(p.progress);
    p.mesh.position.copy(pt);
    p.glow.position.copy(pt);
    p.glow.material.opacity = 0.01 + 0.02 * Math.sin(Date.now() * 0.003 + i);
  }

  renderer.render(scene, camera);
}

// ─── Data Loading ───
function fetchAgents() {
  fetch('/api/activity').then(function(r) { return r.json(); }).then(function(d) {
    var container = document.getElementById('agents-content');
    var activity = d.activity || {};
    var sorted = Object.keys(activity).sort();
    var html = '';
    for (var i = 0; i < sorted.length; i++) {
      var aid = sorted[i];
      var a = activity[aid];
      html += '<div class="card"><div class="name">' + aid + '</div><div class="role">' + (a.topic || '') + '</div>' +
              '<div class="thought"><span class="time">' + (a.timestamp || '').slice(11, 19) + '</span>' + (a.thought || '').substring(0, 80) + '</div></div>';
    }
    if (!html) html = '<div class="card inactive"><div class="name">Aucun agent actif</div></div>';
    container.innerHTML = html;
  }).catch(function(e) {});
}

function fetchMissions() {
  fetch('/api/missions').then(function(r) { return r.json(); }).then(function(d) {
    var container = document.getElementById('missions-content');
    var missions = d.missions || [];
    var html = '';
    for (var i = 0; i < Math.min(missions.length, 10); i++) {
      var m = missions[i];
      var payload = m.payload || {};
      var st = payload.status || 'pending';
      html += '<div class="mission-card ' + st + '"><div class="objective">' + (payload.mission || payload.objective || m.topic).substring(0, 50) + '</div>' +
              '<div class="agent">' + m.source + '</div><div class="status ' + st + '">' + st + '</div></div>';
    }
    if (!html) html = '<div class="mission-card"><div class="objective">Aucune mission</div></div>';
    container.innerHTML = html;
  }).catch(function(e) {});
}

function fetchPackets() {
  fetch('/api/packets').then(function(r) { return r.json(); }).then(function(d) {
    var container = document.getElementById('flow-content');
    var packets = d.packets || [];
    var html = '';
    for (var i = 0; i < Math.min(packets.length, 10); i++) {
      var p = packets[i];
      var t = (p.timestamp || '').slice(11, 19) || '--:--:--';
      var st = p.status || 'done';
      var stClr = st === 'done' ? '#00ff88' : (st === 'failed' ? '#ff4466' : '#ffaa44');
      html += '<div class="flow-row"><span class="t">' + t + '</span><span class="s">' + p.source + '</span><span class="top">' + p.topic + '</span><span class="st" style="background:' + stClr + '22;color:' + stClr + '">' + st + '</span></div>';
    }
    container.innerHTML = html;
  }).catch(function(e) {});
}

// ─── EVA Chat ───
function sendChat() {
  var input = document.getElementById('chat-msg');
  var msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  var container = document.getElementById('chat-messages');
  var userDiv = document.createElement('div');
  userDiv.className = 'chat-msg user';
  userDiv.innerHTML = '<div class="time">' + new Date().toLocaleTimeString() + '</div>' + msg;
  container.appendChild(userDiv);
  container.scrollTop = container.scrollHeight;

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

// ─── Start ───
init();
fetchAgents();
fetchMissions();
fetchPackets();
setInterval(fetchAgents, 5000);
setInterval(fetchMissions, 5000);
setInterval(fetchPackets, 3000);
setInterval(loadGraph, 30000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
