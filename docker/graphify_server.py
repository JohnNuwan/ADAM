#!/usr/bin/env python3
"""Graphify 3D V6 - Network Flow Hub: EVA brain, agents, skills, services + animated packet flows"""
from flask import Flask, jsonify
import psycopg2, json, os, urllib.request, time, threading

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:***@postgres:5432/adam")
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
        time.sleep(15)

threading.Thread(target=refresh_graph, daemon=True).start()

@app.route("/api/graph")
def get_graph():
    with lock:
        return jsonify(nodes_cache)

@app.route("/api/packets")
def get_packets():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return jsonify({"packets": data})
            return jsonify({"packets": data.get("events", [])})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

@app.route("/api/flows")
def get_flows():
    """Return recent packet flow data for animation"""
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=30&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            pkts = data if isinstance(data, list) else data.get("events", [])
            flows = []
            for p in pkts:
                flows.append({
                    "source": p.get("source", ""),
                    "topic": p.get("topic", ""),
                    "timestamp": p.get("timestamp", ""),
                    "status": p.get("status", "done"),
                    "action": p.get("payload", {}).get("action", p.get("payload", {}).get("status", "")),
                })
            return jsonify({"flows": flows})
    except Exception as e:
        return jsonify({"flows": [], "error": str(e)})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM Network Flow Hub</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050510;color:#e0e8f0;font-family:'SF Pro Display','Segoe UI',sans-serif;overflow:hidden}
#app{width:100vw;height:100vh}

#topbar{position:fixed;top:0;left:0;right:0;height:44px;background:linear-gradient(180deg,rgba(5,5,16,0.95),rgba(5,5,16,0.3));display:flex;align-items:center;justify-content:space-between;padding:0 24px;z-index:100;backdrop-filter:blur(10px);border-bottom:1px solid rgba(68,102,136,0.1)}
#topbar .logo{display:flex;align-items:center;gap:10px}
#topbar .logo .dot{width:8px;height:8px;border-radius:50%;background:#00aaff;box-shadow:0 0 12px #00aaff;animation:pulse 2s infinite}
#topbar .logo span{font-size:13px;font-weight:600;letter-spacing:0.5px}
#topbar .stats{display:flex;gap:20px;font-size:11px;color:#5577aa}
#topbar .stats .val{color:#e8e8f0;font-weight:600}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}

#info-panel{position:fixed;top:60px;left:20px;z-index:50;background:rgba(5,5,16,0.93);padding:14px 18px;border-radius:12px;border:1px solid rgba(68,102,136,0.2);max-width:280px;pointer-events:none;opacity:0;transition:all 0.3s;transform:translateY(-5px);backdrop-filter:blur(5px)}
#info-panel.visible{opacity:1;transform:translateY(0)}
#info-panel h3{margin:0 0 2px;font-size:15px;font-weight:600}
#info-panel .tag{display:inline-block;font-size:9px;padding:2px 8px;border-radius:10px;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600}
#info-panel .props{font-size:11px;line-height:1.6;color:#88aacc}
#info-panel .props .k{color:#5577aa;font-size:10px}

#flow-panel{position:fixed;top:60px;right:20px;z-index:50;background:rgba(5,5,16,0.93);padding:12px;border-radius:10px;border:1px solid rgba(68,102,136,0.12);width:280px;max-height:60vh;overflow-y:auto;backdrop-filter:blur(5px)}
#flow-panel::-webkit-scrollbar{width:3px}
#flow-panel::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}
#flow-panel h4{font-size:10px;color:#5577aa;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:6px}
#flow-panel .live-dot{width:5px;height:5px;border-radius:50%;background:#ff4466;animation:pulse 1s infinite}

.flow-row{display:flex;align-items:center;gap:6px;padding:4px 0;border-bottom:1px solid rgba(68,102,136,0.06);font-size:10px;font-family:'SF Mono',Menlo,monospace;color:#88aacc}
.flow-row .src{color:#00ff88;font-weight:600;min-width:65px}
.flow-row .dst{color:#aaccff;min-width:65px}
.flow-row .action{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#6688aa}
.flow-row .st{font-size:8px;padding:1px 4px;border-radius:3px;font-weight:600}
.flow-row .arrow{color:#446688;font-size:8px}

#legend{position:fixed;bottom:20px;left:20px;z-index:50;background:rgba(5,5,16,0.92);padding:10px 14px;border-radius:10px;border:1px solid rgba(68,102,136,0.12)}
#legend h4{font-size:10px;color:#5577aa;margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px}
#legend .item{display:flex;align-items:center;gap:8px;font-size:11px;padding:2px 0;color:#aabbcc}
#legend .dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;box-shadow:0 0 6px currentColor}
#legend .count{color:#446688;font-size:9px;margin-left:auto}

.node-label{position:absolute;font-size:10px;font-weight:500;text-shadow:0 0 4px #000,0 0 8px #000;background:rgba(5,5,16,0.8);padding:2px 6px;border-radius:4px;pointer-events:none;white-space:nowrap;z-index:5;transform:translate(-50%,-50%)}
</style>
</head>
<body>
<div id="app"></div>
<div id="topbar">
  <div class="logo"><div class="dot"></div><span>ADAM Network Flow Hub</span></div>
  <div class="stats" id="stats-bar"></div>
</div>
<div id="info-panel">
  <h3 id="info-name">-</h3>
  <div class="tag" id="info-tag"></div>
  <div class="props" id="info-props"></div>
</div>
<div id="flow-panel"><h4><span class="live-dot"></span>Flux temps reel</h4></div>
<div id="legend"><h4>Legende</h4><div id="legend-items"></div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var scene, camera, renderer, controls;
var nodes = {};
var edges = [];
var flowParticles = [];
var raycaster, pointer;
var selected = null;
var animTime = 0;
var maxFlows = 20;

var NODE_COLORS = {
  'EVA':         {color: 0x00aaff, clr: '#00aaff', size: 1.8, labelSize: '16px', emissive: 0x0066ff},
  'Agent':       {color: 0x00ff88, clr: '#00ff88', size: 0.6, labelSize: '11px', emissive: 0x00cc55},
  'SkillDomain': {color: 0x4488ff, clr: '#4488ff', size: 0.2, labelSize: '8px', emissive: 0x2244aa},
  'Service':     {color: 0xff8844, clr: '#ff8844', size: 0.5, labelSize: '10px', emissive: 0xcc6622}
};

var AGENT_NAMES = {};

function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050510);
  scene.fog = new THREE.FogExp2(0x050510, 0.008);

  camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 500);
  camera.position.set(0, 12, 18);

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  document.getElementById('app').appendChild(renderer.domElement);

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

  // Stars background
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
  Promise.all([
    fetch('/api/graph').then(function(r) { return r.json(); }),
    fetch('/api/flows').then(function(r) { return r.json(); })
  ]).then(function(responses) {
    buildHub(responses[0], responses[1].flows || []);
    animate();
  });
}

function buildHub(graphData, flows) {
  // Clear old nodes
  while(scene.children.length > 6) scene.remove(scene.children[scene.children.length - 1]);

  var graphNodes = graphData.nodes;
  var graphEdges = graphData.edges;
  var legendItems = {};
  var nodePositions = {};

  // Separate nodes by type
  var eva = [], agents = [], skills = [], services = [];
  for (var i = 0; i < graphNodes.length; i++) {
    var n = graphNodes[i];
    if (n.label === 'EVA') eva.push(n);
    else if (n.label === 'Agent') agents.push(n);
    else if (n.label === 'SkillDomain') skills.push(n);
    else if (n.label === 'Service') services.push(n);
  }

  // Layout: EVA at center, agents in a ring, services in inner ring, skills around their agents
  // EVA
  var evaNode = eva[0] || {id:'eva', name:'EVA', label:'EVA', properties:{}};
  var evaPos = new THREE.Vector3(0, 0, 0);
  nodePositions['eva'] = evaPos;

  // Services: inner ring
  var svcRadius = 2.5;
  for (var i = 0; i < services.length; i++) {
    var angle = (2 * Math.PI * i) / services.length;
    nodePositions[services[i].id] = new THREE.Vector3(
      Math.cos(angle) * svcRadius,
      Math.sin(angle) * svcRadius * 0.3,
      Math.sin(angle) * svcRadius
    );
  }

  // Agents: main ring
  var agentRadius = 5.5;
  for (var i = 0; i < agents.length; i++) {
    var angle = (2 * Math.PI * i) / agents.length - Math.PI / 2;
    nodePositions[agents[i].id] = new THREE.Vector3(
      Math.cos(angle) * agentRadius,
      Math.sin(angle * 2) * 0.8,
      Math.sin(angle) * agentRadius
    );
    AGENT_NAMES[agents[i].id] = agents[i].name;
  }

  // Skills: distributed around their parent agents
  // Find which skills connect to which agents via edges
  var skillParents = {};
  for (var i = 0; i < graphEdges.length; i++) {
    var e = graphEdges[i];
    if (e.relation === 'has_skill') {
      skillParents[e.target] = e.source;
    }
  }

  // Count skills per agent for distribution
  var skillCountPerAgent = {};
  for (var sid in skillParents) {
    var pid = skillParents[sid];
    if (!skillCountPerAgent[pid]) skillCountPerAgent[pid] = 0;
    skillCountPerAgent[pid]++;
  }

  var skillIndex = {};
  for (var sid in skillParents) {
    var pid = skillParents[sid];
    if (!skillIndex[pid]) skillIndex[pid] = 0;
    var basePos = nodePositions[pid] || new THREE.Vector3(Math.random()*3, 0, Math.random()*3);
    var count = skillCountPerAgent[pid] || 10;
    var idx = skillIndex[pid]++;
    var angle = (2 * Math.PI * idx) / Math.min(count, 20) + Math.random() * 0.2;
    var dist = 0.8 + Math.random() * 0.5;
    nodePositions[sid] = new THREE.Vector3(
      basePos.x + Math.cos(angle) * dist,
      basePos.y + Math.sin(angle) * dist * 0.5,
      basePos.z + Math.sin(angle) * dist
    );
  }

  // Build nodes
  nodes = {};
  for (var i = 0; i < graphNodes.length; i++) {
    var n = graphNodes[i];
    var pos = nodePositions[n.id] || new THREE.Vector3(Math.random()*5-2.5, Math.random()*5-2.5, Math.random()*5-2.5);
    var cfg = NODE_COLORS[n.label] || NODE_COLORS['SkillDomain'];
    var size = cfg.size;

    // Make EVA bigger
    if (n.label === 'EVA') size = cfg.size;
    else if (n.label === 'Agent') size = cfg.size;
    else if (n.label === 'Service') size = cfg.size;

    var geom = new THREE.SphereGeometry(size, n.label === 'EVA' ? 48 : 20, n.label === 'EVA' ? 48 : 20);
    var mat = new THREE.MeshPhongMaterial({
      color: cfg.color,
      emissive: cfg.emissive || cfg.color,
      emissiveIntensity: n.label === 'EVA' ? 0.6 : (n.label === 'Agent' ? 0.25 : 0.15),
      shininess: 60
    });
    var mesh = new THREE.Mesh(geom, mat);
    mesh.position.copy(pos);
    mesh.userData = {id: n.id, name: n.name, label: n.label, props: n.properties};
    scene.add(mesh);
    nodes[n.id] = mesh;

    // Glow for EVA
    if (n.label === 'EVA') {
      for (var ci = 0; ci < 3; ci++) {
        var glow = new THREE.Mesh(
          new THREE.SphereGeometry(size * (1.2 + ci * 0.25), 32, 32),
          new THREE.MeshBasicMaterial({color: 0x00aaff, transparent: true, opacity: 0.06 - ci * 0.015, side: THREE.BackSide})
        );
        glow.position.copy(pos);
        scene.add(glow);
      }
    }

    // Glow for agents
    if (n.label === 'Agent') {
      var aglow = new THREE.Mesh(
        new THREE.SphereGeometry(size * 1.5, 16, 16),
        new THREE.MeshBasicMaterial({color: cfg.color, transparent: true, opacity: 0.06})
      );
      aglow.position.copy(pos);
      mesh.userData.glow = aglow;
      scene.add(aglow);
    }

    // Label
    var l = document.createElement('div');
    l.className = 'node-label';
    l.textContent = n.label === 'SkillDomain' ? n.name.substring(0, 12) : n.name;
    l.style.color = cfg.clr;
    l.style.fontSize = n.label === 'EVA' ? '16px' : (n.label === 'Agent' ? '11px' : (n.label === 'Service' ? '10px' : '8px'));
    l.style.fontWeight = n.label === 'EVA' ? '700' : '500';
    document.body.appendChild(l);
    mesh.userData.labelEl = l;

    // Legend
    if (!legendItems[n.label]) {
      legendItems[n.label] = {clr: cfg.clr, count: 0};
    }
    legendItems[n.label].count++;
  }

  // Build edges (with animation paths)
  edges = [];
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
        var line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({color: 0x446688, transparent: true, opacity: opacity})
        );
        scene.add(line);
        edges.push({source: e.source, target: e.target, curve: curve, dist: dist});
      }
    }
  }

  // Build flow particles from recent events
  buildFlows(flows);

  // Legend
  var leg = document.getElementById('legend-items');
  leg.innerHTML = '';
  var items = [
    {clr: '#00aaff', label: 'EVA (Cerveau)', count: eva.length},
    {clr: '#00ff88', label: 'Agents', count: agents.length},
    {clr: '#4488ff', label: 'Skills', count: skills.length},
    {clr: '#ff8844', label: 'Services', count: services.length}
  ];
  for (var i = 0; i < items.length; i++) {
    var d = document.createElement('div');
    d.className = 'item';
    d.innerHTML = '<span class="dot" style="background:' + items[i].clr + ';color:' + items[i].clr + '"></span>' + items[i].label + '<span class="count">' + items[i].count + '</span>';
    leg.appendChild(d);
  }

  // Stats bar
  var sb = document.getElementById('stats-bar');
  sb.innerHTML = '<div>Noeuds: <span class="val">' + graphNodes.length + '</span></div>' +
                 '<div>Aretes: <span class="val">' + edges.length + '</span></div>' +
                 '<div>Flux: <span class="val">' + flows.length + '</span></div>';

  console.log('Hub built: ' + graphNodes.length + ' nodes, ' + edges.length + ' edges');
}

function buildFlows(flows) {
  // Remove old particles
  flowParticles.forEach(function(p) { scene.remove(p); });
  flowParticles = [];

  var count = Math.min(flows.length, maxFlows);
  for (var i = 0; i < count; i++) {
    var f = flows[i];
    var srcNode = null, dstNode = null;

    // Find source and destination nodes
    var srcName = f.source || '';
    if (srcName.includes('adam-') || srcName === 'system') {
      // Try to find by name substring
      for (var key in nodes) {
        var n = nodes[key];
        if (n.userData.name && n.userData.name.toLowerCase().includes(srcName.replace('adam-', ''))) {
          srcNode = n;
          break;
        }
      }
    }

    // Destination: try to match topic
    var topic = f.topic || '';
    if (topic.includes('packet') || topic.includes('mission')) {
      // Pick EVA as destination
      dstNode = nodes['eva'] || nodes[Object.keys(nodes).find(k => nodes[k].userData.label === 'EVA')];
    } else if (topic.includes('knowledge') || topic.includes('heartbeat')) {
      dstNode = nodes['eva'] || nodes[Object.keys(nodes).find(k => nodes[k].userData.label === 'EVA')];
    }

    if (!srcNode) {
      // Fallback: use first agent found
      srcNode = nodes[Object.keys(nodes).find(function(k) { return nodes[k].userData.label === 'Agent'; })];
    }
    if (!dstNode) srcNode = null;

    if (srcNode && dstNode && srcNode !== dstNode) {
      var s = srcNode.position.clone();
      var t = dstNode.position.clone();
      var mid = new THREE.Vector3().addVectors(s, t).multiplyScalar(0.5);
      var size = 0.04 + Math.random() * 0.04;
      var geom = new THREE.SphereGeometry(size, 8, 8);
      var mat = new THREE.MeshBasicMaterial({
        color: f.status === 'timeout' ? 0xff4466 : (f.status === 'failed' ? 0xff6644 : 0x00ff88),
        transparent: true,
        opacity: 0.6 + Math.random() * 0.2
      });
      var particle = new THREE.Mesh(geom, mat);
      scene.add(particle);
      flowParticles.push({
        mesh: particle,
        curve: new THREE.QuadraticBezierCurve3(s, mid, t),
        progress: i / count,
        speed: 0.005 + Math.random() * 0.008,
        glow: new THREE.Mesh(
          new THREE.SphereGeometry(size * 3, 8, 8),
          new THREE.MeshBasicMaterial({color: 0x00ff88, transparent: true, opacity: 0.02})
        )
      });
      scene.add(flowParticles[flowParticles.length - 1].glow);
    }
  }

  // Add flow to panel
  var panel = document.getElementById('flow-panel');
  panel.innerHTML = '<h4><span class="live-dot"></span>Flux temps reel</h4>';
  for (var i = 0; i < count; i++) {
    var f = flows[i];
    var div = document.createElement('div');
    div.className = 'flow-row';
    var src = (f.source || '').split('/')[0].substring(0, 12);
    var dst = (f.topic || '').split(':').pop() || 'hub';
    var act = (f.action || f.status || '').substring(0, 15);
    var st = f.status || 'done';
    var stClr = st === 'done' ? '#00ff88' : (st === 'timeout' ? '#ff4466' : '#ffaa44');
    div.innerHTML = '<span class="src">' + src + '</span><span class="arrow">→</span><span class="dst">' + dst + '</span><span class="action">' + act + '</span><span class="st" style="background:' + stClr + '22;color:' + stClr + '">' + st + '</span>';
    panel.appendChild(div);
  }
}

function updateLabels() {
  for (var key in nodes) {
    var mesh = nodes[key];
    if (mesh.userData.labelEl) {
      var pos = mesh.position.clone();
      pos.project(camera);
      if (pos.z < 1) {
        var x = (pos.x * 0.5 + 0.5) * window.innerWidth;
        var y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
        mesh.userData.labelEl.style.left = x + 'px';
        mesh.userData.labelEl.style.top = y + 'px';
        var dist = camera.position.distanceTo(mesh.position);
        if (mesh.userData.label === 'SkillDomain' && dist > 20) {
          mesh.userData.labelEl.style.display = 'none';
        } else if (dist > 35) {
          mesh.userData.labelEl.style.display = 'none';
        } else {
          mesh.userData.labelEl.style.display = 'block';
        }
      } else {
        mesh.userData.labelEl.style.display = 'none';
      }
    }
  }
}

function animateFlows() {
  animTime += 0.02;
  for (var i = 0; i < flowParticles.length; i++) {
    var p = flowParticles[i];
    p.progress += p.speed;
    if (p.progress > 1) p.progress = 0;

    var pt = p.curve.getPoint(p.progress);
    p.mesh.position.copy(pt);
    p.glow.position.copy(pt);

    // Pulse glow
    p.glow.material.opacity = 0.01 + 0.03 * Math.sin(Date.now() * 0.003 + i);
  }

  // Pulse EVA
  if (nodes['eva']) {
    nodes['eva'].material.emissiveIntensity = 0.5 + 0.3 * Math.sin(Date.now() * 0.002);
  }
}

function onClick(event) {
  var rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  var hits = raycaster.intersectObjects(scene.children.filter(function(c) {
    return c.isMesh && c.geometry && c.geometry.type === 'SphereGeometry' && c.userData.name;
  }));
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
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  animateFlows();
  updateLabels();
  renderer.render(scene, camera);
}

function refreshFlows() {
  fetch('/api/flows').then(function(r) { return r.json(); }).then(function(d) {
    if (d.flows && d.flows.length) {
      buildFlows(d.flows);
    }
  }).catch(function(e) {});
}

setInterval(function() { loadGraph(); }, 30000);
setInterval(refreshFlows, 3000);
init();
refreshFlows();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
