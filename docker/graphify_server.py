#!/usr/bin/env python3
"""Graphify 3D V3 - Cluster layout + design premium"""
from flask import Flask, jsonify
import psycopg2, json, os, urllib.request, time, threading, math
from collections import defaultdict

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
            print(f"[REFRESH ERROR] {e}", flush=True)
        time.sleep(10)

threading.Thread(target=refresh_graph, daemon=True).start()

@app.route("/api/graph")
def get_graph():
    with lock:
        return jsonify(nodes_cache)

@app.route("/api/packets")
def get_packets():
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=10")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list):
                return jsonify({"packets": data})
            return jsonify({"packets": data.get("events", [])})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

@app.route("/api/clusters")
def get_clusters():
    """Retourne les clusters groupes par label"""
    with lock:
        groups = defaultdict(list)
        for n in nodes_cache["nodes"]:
            groups[n["label"]].append(n)
        return jsonify({"clusters": dict(groups)})

HTML_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM Knowledge Graph 3D</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#070710;color:#e8e8f0;font-family:'SF Pro Display','Segoe UI',system-ui,sans-serif;overflow:hidden}
#app{width:100vw;height:100vh;position:relative}
#app canvas{display:block}

/* Top bar */
#topbar{position:fixed;top:0;left:0;right:0;height:48px;background:linear-gradient(180deg,rgba(7,7,16,0.95),rgba(7,7,16,0.6));display:flex;align-items:center;justify-content:space-between;padding:0 24px;z-index:100;backdrop-filter:blur(10px);border-bottom:1px solid rgba(68,102,136,0.15)}
#topbar .logo{display:flex;align-items:center;gap:10px}
#topbar .logo .dot{width:8px;height:8px;border-radius:50%;background:#00ff88;box-shadow:0 0 10px #00ff88;animation:pulse 2s infinite}
#topbar .logo span{font-size:14px;font-weight:600;letter-spacing:0.5px}
#topbar .stats{display:flex;gap:20px;font-size:12px;color:#6688aa}
#topbar .stats .stat{display:flex;align-items:center;gap:5px}
#topbar .stats .stat .val{color:#e8e8f0;font-weight:600}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

/* Info panel */
#info{position:fixed;top:64px;left:20px;z-index:50;background:rgba(10,10,20,0.9);padding:16px 20px;border-radius:12px;border:1px solid rgba(68,102,136,0.2);max-width:300px;pointer-events:none;opacity:0;transition:all 0.3s;transform:translateY(-5px)}
#info.visible{opacity:1;transform:translateY(0)}
#info h3{margin:0 0 2px;font-size:16px;font-weight:600}
#info .label-tag{display:inline-block;font-size:10px;padding:2px 8px;border-radius:10px;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;font-weight:600}
#info .props{font-size:12px;line-height:1.6;color:#88aacc}
#info .props .k{color:#5577aa;font-size:11px}

/* Legend */
#legend{position:fixed;bottom:20px;left:20px;z-index:50;background:rgba(10,10,20,0.9);padding:12px 16px;border-radius:10px;border:1px solid rgba(68,102,136,0.15)}
#legend h4{font-size:11px;color:#5577aa;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px}
#legend .item{display:flex;align-items:center;gap:8px;font-size:12px;padding:3px 0;color:#aabbcc}
#legend .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;box-shadow:0 0 6px currentColor}
#legend .count{color:#5577aa;font-size:10px;margin-left:auto}

/* Packet stream */
#packet-stream{position:fixed;bottom:20px;right:20px;z-index:50;background:rgba(10,10,20,0.9);padding:14px;border-radius:10px;border:1px solid rgba(68,102,136,0.15);width:360px;max-height:340px;overflow-y:auto}
#packet-stream::-webkit-scrollbar{width:4px}
#packet-stream::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}
#packet-stream h4{font-size:11px;color:#5577aa;margin-bottom:8px;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:6px}
#packet-stream .live-dot{width:6px;height:6px;border-radius:50%;background:#ff4466;animation:pulse 1s infinite}
.pkt{color:#88aacc;padding:4px 0;border-bottom:1px solid rgba(68,102,136,0.08);font-size:11px;font-family:'SF Mono',Menlo,monospace;display:flex;align-items:center;gap:6px}
.pkt .t{color:#446688;font-size:10px;min-width:55px}
.pkt .s{color:#00ff88;font-weight:600;min-width:70px}
.pkt .top{color:#aaccff;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pkt .st{font-size:9px;padding:1px 5px;border-radius:3px;font-weight:600;text-transform:uppercase}

/* Node labels */
.node-label{position:absolute;font-size:10px;font-weight:500;text-shadow:0 0 4px #000,0 0 8px #000;background:rgba(7,7,16,0.8);padding:2px 7px;border-radius:4px;pointer-events:none;white-space:nowrap;z-index:5;transform:translate(-50%,-50%);letter-spacing:0.2px}

/* Controls hint */
#hint{position:fixed;bottom:20px;right:400px;z-index:50;font-size:10px;color:#334455;line-height:1.8;text-align:right}

/* Cluster labels */
.cluster-label{position:absolute;font-size:18px;font-weight:200;letter-spacing:2px;text-transform:uppercase;pointer-events:none;z-index:4;opacity:0.3;text-shadow:0 0 20px currentColor}
</style>
</head>
<body>
<div id="app"></div>
<div id="topbar">
  <div class="logo"><div class="dot"></div><span>ADAM Knowledge Graph</span></div>
  <div class="stats" id="stats-bar"></div>
</div>
<div id="info">
  <h3 id="info-name">-</h3>
  <div class="label-tag" id="info-tag"></div>
  <div class="props" id="info-props"></div>
</div>
<div id="legend"><h4>Clusters</h4><div id="legend-items"></div></div>
<div id="packet-stream"><h4><span class="live-dot"></span>Flux temps reel</h4></div>
<div id="hint">Glisser: orbiter<br>Molette: zoom<br>Clic noeud: details</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var scene, camera, renderer, controls;
var meshes = {};
var raycaster, pointer;
var selected = null;
var clusterGroups = {};
var clusterMeshes = [];

var CLUSTER_CONFIG = {
  EVA:         {color: 0xffaa00, clr: '#ffaa00', size: 1.0, clusterSize: 1.5},

  Agent:       {color: 0x00ff88, clr: '#00ff88', size: 0.6, clusterSize: 3.5},
  SkillDomain: {color: 0x4488ff, clr: '#4488ff', size: 0.3, clusterSize: 5.0},
  Service:     {color: 0xff8844, clr: '#ff8844', size: 0.5, clusterSize: 2.5}
};

function init() {
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x070710);
  scene.fog = new THREE.Fog(0x070710, 30, 80);

  camera = new THREE.PerspectiveCamera(55, window.innerWidth/window.innerHeight, 0.1, 500);
  camera.position.set(0, 15, 25);

  renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  document.getElementById('app').appendChild(renderer.domElement);

  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.autoRotate = true;
  controls.autoRotateSpeed = 0.4;
  controls.minDistance = 5;
  controls.maxDistance = 60;
  controls.target.set(0, 0, 0);

  raycaster = new THREE.Raycaster();
  pointer = new THREE.Vector2();

  // Lighting
  scene.add(new THREE.DirectionalLight(0xffffff, 1.2));
  var amb = new THREE.AmbientLight(0x222244);
  scene.add(amb);
  // Rim light
  var rim = new THREE.DirectionalLight(0x4466aa, 0.5);
  rim.position.set(-10, 5, -10);
  scene.add(rim);

  // Stars
  var sg = new THREE.BufferGeometry();
  var sp = new Float32Array(4000);
  for (var i = 0; i < 4000; i++) {
    sp[i*3] = (Math.random()-0.5)*300;
    sp[i*3+1] = (Math.random()-0.5)*300;
    sp[i*3+2] = (Math.random()-0.5)*300;
  }
  sg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
  scene.add(new THREE.Points(sg, new THREE.PointsMaterial({color: 0x334466, size: 0.3, transparent: true, opacity: 0.6})));

  renderer.domElement.addEventListener('click', onClick);
  window.addEventListener('resize', onResize);
  loadGraph();
}

function loadGraph() {
  fetch('/api/graph').then(function(r) { return r.json(); }).then(function(data) {
    buildClusters(data);
    animate();
  });
}

function buildClusters(data) {
  // Group nodes by label
  var groups = {};
  for (var i = 0; i < data.nodes.length; i++) {
    var n = data.nodes[i];
    if (!groups[n.label]) groups[n.label] = [];
    groups[n.label].push(n);
  }

  // Place each cluster on a circle around center
  var clusterKeys = Object.keys(groups);
  var numClusters = clusterKeys.length;
  // EVA goes to center, others around it
  var hasEVA = groups['EVA'] !== undefined;
  var nonEVAKeys = clusterKeys.filter(function(k) { return k !== 'EVA'; });
  var numNonEVA = nonEVAKeys.length;
  var clusterRadius = 10 + numNonEVA * 1.5;

  // Build legend
  var leg = document.getElementById('legend-items');
  leg.innerHTML = '';

  var allKeys = hasEVA ? ['EVA'].concat(nonEVAKeys) : nonEVAKeys;
  for (var ci = 0; ci < allKeys.length; ci++) {
    var label = allKeys[ci];
    var nodes = groups[label];
    var cfg = CLUSTER_CONFIG[label] || {color: 0x888888, clr: '#888', size: 0.35, clusterSize: 4};

    // Cluster center position
    var cx, cz, cy = 0;
    if (label === 'EVA') {
      cx = 0; cz = 0;
    } else {
      var idx = hasEVA ? ci - 1 : ci;
      var ca = (2 * Math.PI * idx) / numNonEVA;
      cx = Math.cos(ca) * clusterRadius;
      cz = Math.sin(ca) * clusterRadius;
    }
    var cy = 0;

    // Legend entry
    var d = document.createElement('div');
    d.className = 'item';
    d.innerHTML = '<span class="dot" style="background:' + cfg.clr + ';color:' + cfg.clr + '"></span>' + label + '<span class="count">' + nodes.length + '</span>';
    leg.appendChild(d);

    // Cluster halo (transparent sphere)
    var halo = new THREE.Mesh(
      new THREE.SphereGeometry(cfg.clusterSize, 32, 32),
      new THREE.MeshBasicMaterial({color: cfg.color, transparent: true, opacity: 0.04, side: THREE.BackSide})
    );
    halo.position.set(cx, cy, cz);
    scene.add(halo);
    clusterMeshes.push(halo);

    // Cluster label
    var cl = document.createElement('div');
    cl.className = 'cluster-label';
    cl.textContent = label;
    cl.style.color = cfg.clr;
    document.body.appendChild(cl);
    halo.userData.clusterLabel = cl;
    halo.userData.clusterPos = new THREE.Vector3(cx, cy + cfg.clusterSize + 1, cz);

    // Place nodes in a sphere within the cluster
    for (var ni = 0; ni < nodes.length; ni++) {
      var n = nodes[ni];
      var phi = Math.acos(1 - 2 * (ni + 0.5) / nodes.length);
      var theta = Math.PI * (1 + Math.sqrt(5)) * ni;
      var r = cfg.clusterSize * 0.7 * Math.sqrt(Math.random() * 0.5 + 0.5);

      var pos = new THREE.Vector3(
        cx + r * Math.sin(phi) * Math.cos(theta),
        cy + r * Math.sin(phi) * Math.sin(theta),
        cz + r * Math.cos(phi)
      );

      var size = cfg.size * (n.label === 'Agent' ? 1 : (0.7 + Math.random() * 0.4));
      var mesh = new THREE.Mesh(
        new THREE.SphereGeometry(size, 24, 24),
        new THREE.MeshPhongMaterial({color: cfg.color, emissive: cfg.color, emissiveIntensity: 0.12, shininess: 80})
      );
      mesh.position.copy(pos);
      mesh.userData = {id: n.id, name: n.name, label: n.label, props: n.properties, clusterCenter: new THREE.Vector3(cx, cy, cz)};
      scene.add(mesh);
      meshes[n.id] = mesh;

      // Glow
      var glow = new THREE.Mesh(
        new THREE.SphereGeometry(size * 1.6, 16, 16),
        new THREE.MeshBasicMaterial({color: cfg.color, transparent: true, opacity: 0.06})
      );
      glow.position.copy(pos);
      scene.add(glow);

      // HTML label
      var l = document.createElement('div');
      l.className = 'node-label';
      l.textContent = n.name;
      l.style.color = cfg.clr;
      l.style.borderColor = cfg.clr + '33';
      document.body.appendChild(l);
      mesh.userData.labelEl = l;
    }
  }

  // Edges
  var edgeCount = 0;
  for (var i = 0; i < data.edges.length; i++) {
    var e = data.edges[i];
    if (meshes[e.source] && meshes[e.target]) {
      var s = meshes[e.source].position;
      var t = meshes[e.target].position;
      var dist = s.distanceTo(t);
      // Only draw edges within reasonable distance
      if (dist < 25) {
        var mid = new THREE.Vector3().addVectors(s, t).multiplyScalar(0.5);
        mid.y += dist * 0.05;
        var pts = new THREE.QuadraticBezierCurve3(s, mid, t).getPoints(15);
        var opacity = Math.max(0.05, 0.3 - dist * 0.01);
        scene.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({color: 0x446688, transparent: true, opacity: opacity})
        ));
      }
      edgeCount++;
    }
  }

  // Update stats bar
  var sb = document.getElementById('stats-bar');
  sb.innerHTML = '<div class="stat">Noeuds: <span class="val">' + data.nodes.length + '</span></div>' +
                 '<div class="stat">Aretes: <span class="val">' + edgeCount + '</span></div>' +
                 '<div class="stat">Clusters: <span class="val">' + numClusters + '</span></div>';

  console.log('Built: ' + data.nodes.length + ' nodes, ' + edgeCount + ' edges, ' + numClusters + ' clusters');
}

function updateLabels() {
  // Node labels
  for (var key in meshes) {
    var mesh = meshes[key];
    if (mesh.userData.labelEl) {
      var pos = mesh.position.clone();
      pos.project(camera);
      if (pos.z < 1) {
        var x = (pos.x * 0.5 + 0.5) * window.innerWidth;
        var y = (-pos.y * 0.5 + 0.5) * window.innerHeight;
        mesh.userData.labelEl.style.left = x + 'px';
        mesh.userData.labelEl.style.top = y + 'px';
        // Hide labels that are too far
        var dist = camera.position.distanceTo(mesh.position);
        mesh.userData.labelEl.style.display = dist < 35 ? 'block' : 'none';
      } else {
        mesh.userData.labelEl.style.display = 'none';
      }
    }
  }
  // Cluster labels
  for (var i = 0; i < clusterMeshes.length; i++) {
    var cm = clusterMeshes[i];
    if (cm.userData.clusterLabel && cm.userData.clusterPos) {
      var pos = cm.userData.clusterPos.clone();
      pos.project(camera);
      if (pos.z < 1) {
        cm.userData.clusterLabel.style.left = ((pos.x * 0.5 + 0.5) * window.innerWidth) + 'px';
        cm.userData.clusterLabel.style.top = ((-pos.y * 0.5 + 0.5) * window.innerHeight) + 'px';
        cm.userData.clusterLabel.style.display = 'block';
      } else {
        cm.userData.clusterLabel.style.display = 'none';
      }
    }
  }
}

function onClick(event) {
  var rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);
  var hits = raycaster.intersectObjects(scene.children.filter(function(c) {
    return c.isMesh && c.geometry && c.geometry.type === 'SphereGeometry';
  }));
  if (hits.length > 0 && hits[0].object.userData.name) {
    var o = hits[0].object;
    var cfg = CLUSTER_CONFIG[o.userData.label] || {clr: '#888'};
    document.getElementById('info-name').textContent = o.userData.name;
    var tag = document.getElementById('info-tag');
    tag.textContent = o.userData.label;
    tag.style.background = cfg.clr + '22';
    tag.style.color = cfg.clr;
    var p = o.userData.props || {};
    var html = '';
    for (var k in p) { html += '<div><span class="k">' + k + '</span> ' + p[k] + '</div>'; }
    document.getElementById('info-props').innerHTML = html || 'Aucune propriete';
    document.getElementById('info').classList.add('visible');
    if (selected) selected.material.emissiveIntensity = 0.12;
    selected = o;
    selected.material.emissiveIntensity = 0.5;
  } else {
    document.getElementById('info').classList.remove('visible');
    if (selected) { selected.material.emissiveIntensity = 0.12; selected = null; }
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
  if (selected) selected.material.emissiveIntensity = 0.4 + 0.2 * Math.sin(Date.now() * 0.004);
  // Pulse cluster halos
  for (var i = 0; i < clusterMeshes.length; i++) {
    clusterMeshes[i].material.opacity = 0.03 + 0.02 * Math.sin(Date.now() * 0.001 + i);
  }
  renderer.render(scene, camera);
  updateLabels();
}

// Packet stream
function fetchPackets() {
  fetch('/api/packets').then(function(r) { return r.json(); }).then(function(d) {
    if (!d.packets || !d.packets.length) return;
    var c = document.getElementById('packet-stream');
    c.innerHTML = '<h4><span class="live-dot"></span>Flux temps reel</h4>';
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

// Auto-refresh graph every 30s
setInterval(function() { loadGraph(); }, 30000);

init();
setInterval(fetchPackets, 3000);
fetchPackets();
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML_PAGE

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8090)
