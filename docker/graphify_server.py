#!/usr/bin/env python3
"""Graphify 3D V2.1 — Knowledge Graph avec flux paquets temps réel"""
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
            cur.execute("SELECT source_id, target_id, relation FROM knowledge_edges LIMIT 1000")
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

@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ADAM Graph — Knowledge Graph 3D</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a0f;color:#e0e0e8;font-family:'Segoe UI',system-ui,sans-serif;overflow:hidden}
#app{width:100vw;height:100vh}
#info{position:fixed;top:20px;left:20px;z-index:10;background:rgba(10,10,15,0.85);padding:16px 20px;border-radius:12px;border:1px solid rgba(68,102,136,0.3);max-width:320px;pointer-events:none;opacity:0;transition:opacity 0.3s}
#info.visible{opacity:1}
#info h3{margin:0 0 4px;font-size:18px;color:#00ff88}
#info .label{font-size:12px;color:#6688aa}
#info .props{font-size:13px;line-height:1.5;color:#88aacc}
#legend{position:fixed;bottom:20px;left:20px;z-index:10;background:rgba(10,10,15,0.85);padding:12px 16px;border-radius:8px;border:1px solid rgba(68,102,136,0.3)}
#legend h4{font-size:13px;color:#6688aa;margin-bottom:6px}
#legend .item{display:flex;align-items:center;gap:8px;font-size:12px;padding:2px 0}
#legend .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
#title{position:fixed;top:20px;right:20px;z-index:10;text-align:right}
#title h1{font-size:20px;font-weight:300;color:#e0e0e8}
#title p{font-size:11px;color:#446688}
#packet-stream{position:fixed;bottom:20px;right:20px;z-index:10;background:rgba(10,10,15,0.85);padding:12px;border-radius:8px;border:1px solid rgba(68,102,136,0.3);max-height:300px;width:340px;overflow-y:auto;font-size:11px;font-family:monospace;color:#88aacc}
#packet-stream h4{color:#6688aa;margin-bottom:6px;font-size:12px}
.pkt{color:#88aacc;padding:3px 0;border-bottom:1px solid rgba(68,102,136,0.1)}
.pkt .t{color:#446688}
.pkt .s{color:#00ff88}
.pkt .st{color:#ff8844}
#controls-hint{position:fixed;bottom:20px;right:380px;z-index:10;font-size:11px;color:#335577;line-height:1.6}
</style>
</head>
<body>
<div id="app"></div>
<div id="title"><h1>🐝 Knowledge Graph</h1><p>ADAM — The Hive</p></div>
<div id="info"><h3 id="info-name">—</h3><div class="label" id="info-label"></div><div class="props"><span id="info-props"></span></div></div>
<div id="legend"></div>
<div id="packet-stream"><h4>📦 Flux paquets temps réel</h4></div>
<div id="controls-hint">🖱 Glisser pour orbiter · Clic nœud → infos</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
(async()=>{
const res=await fetch('/api/graph'),data=await res.json();
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(50,window.innerWidth/window.innerHeight,0.1,500);
camera.position.set(22,16,28);
const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(window.innerWidth,window.innerHeight);
document.getElementById('app').appendChild(renderer.domElement);
const controls=new THREE.OrbitControls(camera,renderer.domElement);
controls.enableDamping=true;controls.dampingFactor=0.08;
controls.autoRotate=true;controls.autoRotateSpeed=0.6;
controls.minDistance=8;controls.maxDistance=60;

const COLOR_MAP={Agent:0x00ff88,SkillDomain:0x4488ff,Service:0xff8844};
const LABEL_CLR={Agent:'#00ff88',SkillDomain:'#4488ff',Service:'#ff8844'};
const meshes={},positions={};
const leg=document.getElementById('legend');
leg.innerHTML='<h4>Légende</h4>';
const seen=new Set();

data.nodes.forEach(n=>{
  if(!seen.has(n.label)){seen.add(n.label);
    const d=document.createElement('div');d.className='item';
    d.innerHTML='<span class="dot" style="background:'+(LABEL_CLR[n.label]||'#888')+'"></span>'+n.label;
    leg.appendChild(d);}
});

data.nodes.forEach((n,i)=>{
  const angle=(2*Math.PI*i)/data.nodes.length+Math.random()*0.3;
  const tilt=(Math.random()-0.5)*Math.PI*0.6;
  const pos=new THREE.Vector3(
    Math.cos(angle)*8+Math.random()*2,Math.sin(tilt)*6,
    Math.sin(angle)*8+Math.random()*2);
  positions[n.id]=pos;
  const color=COLOR_MAP[n.label]||0x888888;
  const size=n.label==='Agent'?0.55:0.35;
  const mesh=new THREE.Mesh(
    new THREE.SphereGeometry(size,20,20),
    new THREE.MeshPhongMaterial({color,emissive:color,emissiveIntensity:0.15}));
  mesh.position.copy(pos);
  mesh.userData={id:n.id,name:n.name,label:n.label,props:n.properties};
  scene.add(mesh);
  meshes[n.id]=mesh;
  const g=new THREE.Mesh(new THREE.SphereGeometry(size*1.8,16,16),
    new THREE.MeshBasicMaterial({color,transparent:true,opacity:0.08}));
  g.position.copy(pos);scene.add(g);
  // Label
  const l=document.createElement('div');
  l.textContent=n.name;
  l.style.cssText='color:'+(LABEL_CLR[n.label]||'#888')+';font-size:12px;font-weight:500;text-shadow:0 0 8px #000;background:rgba(10,10,15,0.7);padding:2px 8px;border-radius:4px;pointer-events:none;white-space:nowrap';
  const lbl=new THREE.CSS2DObject(l);
  lbl.position.set(pos.x,pos.y-size-0.6,pos.z);
  scene.add(lbl);
});

data.edges.forEach(e=>{
  if(meshes[e.source]&&meshes[e.target]){
    const s=meshes[e.source].position,t=meshes[e.target].position;
    const m=new THREE.Vector3().addVectors(s,t).multiplyScalar(0.5);m.y+=0.5;
    const pts=new THREE.QuadraticBezierCurve3(s,m,t).getPoints(20);
    const g=new THREE.BufferGeometry().setFromPoints(pts);
    scene.add(new THREE.Line(g,new THREE.LineBasicMaterial({color:0x446688,transparent:true,opacity:0.25})));
  }
});

// Stars
const sg=new THREE.BufferGeometry();
const sp=new Float32Array(3000);
for(let i=0;i<3000;i++){sp[i*3]=(Math.random()-0.5)*200;sp[i*3+1]=(Math.random()-0.5)*200;sp[i*3+2]=(Math.random()-0.5)*200;}
sg.setAttribute('position',new THREE.BufferAttribute(sp,3));
scene.add(new THREE.Points(sg,new THREE.PointsMaterial({color:0x446688,size:0.5,transparent:true,opacity:0.5})));
scene.add(new THREE.DirectionalLight(0xffffff,1.5));
scene.add(new THREE.AmbientLight(0x222244));

// Click handler
const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();
let selected=null;
renderer.domElement.addEventListener('click',e=>{
  const rect=renderer.domElement.getBoundingClientRect();
  pointer.x=((e.clientX-rect.left)/rect.width)*2-1;
  pointer.y=-((e.clientY-rect.top)/rect.height)*2+1;
  raycaster.setFromCamera(pointer,camera);
  const hits=raycaster.intersectObjects(scene.children.filter(c=>c.isMesh&&c.geometry.type==='SphereGeometry'));
  if(hits.length&&hits[0].object.userData.name){
    const o=hits[0].object;
    document.getElementById('info-name').textContent=o.userData.name;
    document.getElementById('info-label').textContent=o.userData.label;
    const p=o.userData.props||{};
    document.getElementById('info-props').innerHTML=Object.entries(p).map(([k,v])=>'<span>'+k+':</span> '+v).join('<br>')||'<span>Aucune propriété</span>';
    document.getElementById('info').classList.add('visible');
    if(selected)selected.material.emissiveIntensity=0.15;
    selected=o;selected.material.emissiveIntensity=0.4;
  }else{
    document.getElementById('info').classList.remove('visible');
    if(selected){selected.material.emissiveIntensity=0.15;selected=null;}
  }
});

function animate(){
  requestAnimationFrame(animate);
  controls.update();
  if(selected)selected.material.emissiveIntensity=0.3+0.2*Math.sin(Date.now()*0.005);
  renderer.render(scene,camera);
}
animate();
window.addEventListener('resize',()=>{camera.aspect=window.innerWidth/window.innerHeight;camera.updateProjectionMatrix();renderer.setSize(window.innerWidth,window.innerHeight);});
})();
</script>
<script>
// Packet stream - separate from Three.js to avoid conflicts
const pktContainer=document.getElementById('packet-stream');
async function fetchPackets(){
  try{
    const r=await fetch('/api/packets'),d=await r.json();
    if(!d.packets||!d.packets.length)return;
    pktContainer.innerHTML='<h4>📦 Flux paquets temps réel</h4>';
    d.packets.slice(0,8).forEach(p=>{
      const div=document.createElement('div');div.className='pkt';
      const t=(p.timestamp||'').slice(11,19)||new Date().toLocaleTimeString();
      div.innerHTML='<span class="t">'+t+'</span> <span class="s">'+p.source+'</span> → '+p.topic+' <span class="st">'+(p.status||'done')+'</span>';
      pktContainer.appendChild(div);
    });
  }catch(e){}
}
setInterval(fetchPackets,3000);
fetchPackets();
</script>
</body>
</html>"""

if __name__=="__main__":
    app.run(host="0.0.0.0",port=8090)
