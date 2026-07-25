#!/usr/bin/env python3
"""Graphify 3D V2 — Visualisation du knowledge graph ADAM avec labels + interactions"""
from flask import Flask, jsonify, send_from_directory
import psycopg2, json, os

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:***@postgres:5432/adam")

@app.route("/api/graph")


def get_graph():
    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()
    nodes = []
    cur.execute("SELECT id, label, name, properties FROM knowledge_nodes LIMIT 500")
    for row in cur:
        props = row[3] or {}
        nodes.append({"id": str(row[0]), "label": row[1], "name": row[2], "properties": props if isinstance(props, dict) else {}})
    edges = []
    cur.execute("SELECT source_id, target_id, relation FROM knowledge_edges LIMIT 1000")
    for row in cur:
        edges.append({"source": str(row[0]), "target": str(row[1]), "relation": row[2]})
    cur.close()
    pg.close()
    return jsonify({"nodes": nodes, "edges": edges})

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
#info .label{font-size:12px;color:#6688aa;margin-bottom:8px}
#info .props{font-size:13px;line-height:1.5}
#info .props span{color:#88aacc}
#legend{position:fixed;bottom:20px;left:20px;z-index:10;background:rgba(10,10,15,0.85);padding:12px 16px;border-radius:8px;border:1px solid rgba(68,102,136,0.3)}
#legend h4{font-size:13px;color:#6688aa;margin-bottom:6px}
#legend .item{display:flex;align-items:center;gap:8px;font-size:12px;padding:2px 0}
#legend .dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
#title{position:fixed;top:20px;right:20px;z-index:10;text-align:right}
#title h1{font-size:20px;font-weight:300;color:#e0e0e8}
#title p{font-size:11px;color:#446688;margin-top:2px}
#controls-hint{position:fixed;bottom:20px;right:20px;z-index:10;font-size:11px;color:#335577;text-align:right;line-height:1.6}
</style>
</head>
<body>
<div id="app"></div>

<div id="title">
  <h1>🐝 Knowledge Graph</h1>
  <p>ADAM — The Hive</p>
</div>

<div id="info">
  <h3 id="info-name">—</h3>
  <div class="label" id="info-label"></div>
  <div class="props"><span id="info-props"></span></div>
</div>

<div id="legend"></div>

<div id="controls-hint">🖱 Faire glisser pour orbiter<br>🖱 Clic sur un nœud pour voir les infos</div>

<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.170.0/examples/jsm/"
  }
}
</script>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

(async()=>{
const res=await fetch('/api/graph');
const data=await res.json();

const scene=new THREE.Scene();
scene.background=new THREE.Color(0x0a0a0f);

const camera=new THREE.PerspectiveCamera(60,window.innerWidth/window.innerHeight,0.1,1000);
camera.position.set(22,16,28);

const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(window.innerWidth,window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
renderer.shadowMap.enabled=true;
document.getElementById('app').appendChild(renderer.domElement);

const labelRenderer=new CSS2DRenderer();
labelRenderer.setSize(window.innerWidth,window.innerHeight);
labelRenderer.domElement.style.position='absolute';
labelRenderer.domElement.style.top='0';
labelRenderer.domElement.style.left='0';
labelRenderer.domElement.style.pointerEvents='none';
document.getElementById('app').appendChild(labelRenderer.domElement);

const controls=new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true;
controls.dampingFactor=0.08;
controls.autoRotate=true;
controls.autoRotateSpeed=0.6;
controls.minDistance=8;
controls.maxDistance=60;

// Colors by label
const ColorMap={
  'Agent':  0x00ff88,
  'Service':0x4488ff,
  'Topic':  0xff8844,
  'Project':0xff44ff,
  'Concept':0x44ff88,
  'Person': 0xffaa44,
  'Skill':  0xff44ff,
  'Tool':   0x44ccff,
};

const labelColors={
  'Agent':  '#00ff88',
  'Service':'#4488ff',
  'Topic':  '#ff8844',
  'Project':'#ff44ff',
  'Concept':'#44ff88',
  'Person': '#ffaa44',
  'Skill':  '#ff44ff',
  'Tool':   '#44ccff',
};

// Build legend
const legend=document.getElementById('legend');
legend.innerHTML='<h4>Légende</h4>';
const seenLabels=new Set();
data.nodes.forEach(n=>{
  if(!seenLabels.has(n.label)){
    seenLabels.add(n.label);
    const div=document.createElement('div');
    div.className='item';
    div.innerHTML='<span class="dot" style="background:'+(labelColors[n.label]||'#888')+'"></span>'+n.label;
    legend.appendChild(div);
  }
});

// Force-directed simulation (simple 3D)
const nodeMap={};
const positions={};
const velocities={};
const radius=6;

data.nodes.forEach((n,i)=>{
  const angle=(2*Math.PI*i)/data.nodes.length+Math.random()*0.3;
  const tilt=Math.PI*(Math.random()-0.5)*0.6;
  positions[n.id]=new THREE.Vector3(
    Math.cos(angle)*radius+Math.random()*2,
    Math.sin(tilt)*radius*0.8,
    Math.sin(angle)*radius+Math.random()*2
  );
  velocities[n.id]=new THREE.Vector3(0,0,0);
});

// Simulate force-directed layout (few iterations)
for(let iter=0;iter<50;iter++){
  // Repulsion between all nodes
  const ids=Object.keys(positions);
  for(let i=0;i<ids.length;i++){
    for(let j=i+1;j<ids.length;j++){
      const a=ids[i],b=ids[j];
      const diff=new THREE.Vector3().copy(positions[a]).sub(positions[b]);
      const dist=Math.max(diff.length(),0.5);
      const force=2/(dist*dist);
      diff.normalize().multiplyScalar(force);
      velocities[a].add(diff);
      velocities[b].sub(diff);
    }
  }
  // Attraction along edges
  data.edges.forEach(e=>{
    if(positions[e.source]&&positions[e.target]){
      const diff=new THREE.Vector3().copy(positions[e.target]).sub(positions[e.source]);
      const dist=diff.length();
      const force=dist*0.02;
      diff.normalize().multiplyScalar(force);
      velocities[e.source].add(diff);
      velocities[e.target].sub(diff);
    }
  });
  // Center gravity
  ids.forEach(id=>{
    velocities[id].add(new THREE.Vector3().copy(positions[id]).multiplyScalar(-0.01));
    // Update
    positions[id].add(velocities[id]);
    velocities[id].multiplyScalar(0.85);
  });
}

// Create nodes
const meshes={};
data.nodes.forEach(n=>{
  const color=ColorMap[n.label]||0x888888;
  const size=n.label==='Agent'?0.55:0.35;
  const geom=new THREE.SphereGeometry(size,20,20);
  const mat=new THREE.MeshPhongMaterial({color,emissive:color,emissiveIntensity:0.15,shininess:60});
  const mesh=new THREE.Mesh(geom,mat);
  mesh.position.copy(positions[n.id]);
  mesh.userData={id:n.id,name:n.name,label:n.label,props:n.properties};
  scene.add(mesh);
  meshes[n.id]=mesh;

  // Glow halo
  const glowGeom=new THREE.SphereGeometry(size*1.8,16,16);
  const glowMat=new THREE.MeshBasicMaterial({color,transparent:true,opacity:0.08});
  const glow=new THREE.Mesh(glowGeom,glowMat);
  glow.position.copy(positions[n.id]);
  scene.add(glow);

  // Label
  const labelDiv=document.createElement('div');
  labelDiv.textContent=n.name;
  labelDiv.style.color=labelColors[n.label]||'#888';
  labelDiv.style.fontSize='12px';
  labelDiv.style.fontWeight='500';
  labelDiv.style.textShadow='0 0 8px rgba(0,0,0,0.9)';
  labelDiv.style.background='rgba(10,10,15,0.6)';
  labelDiv.style.padding='2px 8px';
  labelDiv.style.borderRadius='4px';
  labelDiv.style.border='1px solid '+(labelColors[n.label]||'#888')+'33';
  labelDiv.style.pointerEvents='none';
  labelDiv.style.whiteSpace='nowrap';
  const label=new CSS2DObject(labelDiv);
  label.position.set(positions[n.id].x,positions[n.id].y-size-0.6,positions[n.id].z);
  scene.add(label);
});

// Edges
data.edges.forEach(e=>{
  if(meshes[e.source]&&meshes[e.target]){
    const start=meshes[e.source].position;
    const end=meshes[e.target].position;
    // Curved line
    const mid=new THREE.Vector3().addVectors(start,end).multiplyScalar(0.5);
    mid.y+=0.5;
    const curve=new THREE.QuadraticBezierCurve3(start,mid,end);
    const pts=curve.getPoints(20);
    const geom=new THREE.BufferGeometry().setFromPoints(pts);
    const mat=new THREE.LineBasicMaterial({color:0x446688,transparent:true,opacity:0.25});
    scene.add(new THREE.Line(geom,mat));

    // Arrow end (small sphere)
    const arrowGeom=new THREE.SphereGeometry(0.08,8,8);
    const arrowMat=new THREE.MeshBasicMaterial({color:0x6688aa,transparent:true,opacity:0.4});
    const arrow=new THREE.Mesh(arrowGeom,arrowMat);
    arrow.position.copy(end);
    scene.add(arrow);
  }
});

// Stars background
const starsGeom=new THREE.BufferGeometry();
const starsPos=new Float32Array(3000);
for(let i=0;i<3000;i++){
  starsPos[i*3]=(Math.random()-0.5)*200;
  starsPos[i*3+1]=(Math.random()-0.5)*200;
  starsPos[i*3+2]=(Math.random()-0.5)*200;
}
starsGeom.setAttribute('position',new THREE.BufferAttribute(starsPos,3));
const starsMat=new THREE.PointsMaterial({color:0x446688,size:0.5,transparent:true,opacity:0.5});
scene.add(new THREE.Points(starsGeom,starsMat));

// Lighting
const dirLight=new THREE.DirectionalLight(0xffffff,1.5);
dirLight.position.set(10,15,10);
scene.add(dirLight);
const ambLight=new THREE.AmbientLight(0x222244);
scene.add(ambLight);

// Raycaster for click detection
const raycaster=new THREE.Raycaster();
const pointer=new THREE.Vector2();
let selectedNode=null;

renderer.domElement.addEventListener('click',(event)=>{
  const rect=renderer.domElement.getBoundingClientRect();
  pointer.x=((event.clientX-rect.left)/rect.width)*2-1;
  pointer.y=-((event.clientY-rect.top)/rect.height)*2+1;
  raycaster.setFromCamera(pointer,camera);
  const intersects=raycaster.intersectObjects(scene.children.filter(c=>c.isMesh&&c.geometry.type==='SphereGeometry'));
  if(intersects.length>0){
    const obj=intersects[0].object;
    if(obj.userData.name){
      const info=document.getElementById('info');
      document.getElementById('info-name').textContent=obj.userData.name;
      document.getElementById('info-label').textContent=obj.userData.label;
      const props=obj.userData.props||{};
      const propText=Object.entries(props).map(([k,v])=>`<span>${k}:</span> ${v}`).join('<br>');
      document.getElementById('info-props').innerHTML=propText||'<span>Aucune propriété</span>';
      info.classList.add('visible');
      selectedNode=obj;
    }
  }else{
    document.getElementById('info').classList.remove('visible');
    selectedNode=null;
  }
});

// Animate
function animate(){
  requestAnimationFrame(animate);
  controls.update();

  // Pulse selected node
  if(selectedNode){
    const pulse=0.8+0.2*Math.sin(Date.now()*0.005);
    selectedNode.material.emissiveIntensity=pulse*0.3;
  }

  renderer.render(scene,camera);
  labelRenderer.render(scene,camera);
}
animate();

window.addEventListener('resize',()=>{
  camera.aspect=window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth,window.innerHeight);
  labelRenderer.setSize(window.innerWidth,window.innerHeight);
});

// Click on canvas to dismiss info
renderer.domElement.addEventListener('dblclick',()=>{
  document.getElementById('info').classList.remove('visible');
  if(selectedNode){selectedNode.material.emissiveIntensity=0.15;selectedNode=null;}
});

})();
</script>

<div id="packet-stream"><h4 style="color:#6688aa;margin-bottom:6px;font-size:12px;">📦 Flux paquets temps réel</h4></div>
<script>
const pktContainer = document.getElementById("packet-stream");
async function pollPackets(){
  try{
    const r=await fetch("/api/packets"),d=await r.json();
    if(!d.packets||!d.packets.length) return;
    pktContainer.innerHTML = "<h4 style=\"color:#6688aa;margin-bottom:6px;font-size:12px;\">📦 Flux paquets temps réel</h4>";
    d.packets.slice(0,10).forEach(p=>{
      const div=document.createElement("div");
      div.style.cssText="padding:3px 0;border-bottom:1px solid rgba(68,102,136,0.1);font-size:11px;";
      const t=(p.timestamp||"").slice(11,19)||new Date().toLocaleTimeString();
      div.innerHTML='<span style="color:#446688">'+t+'</span> <span style="color:#00ff88">'+p.source+'</span> → '+p.topic+' <span style="color:#ff8844">'+(p.status||"done")+'</span>';
      pktContainer.appendChild(div);
    });
  }catch(e){console.log(e)}
}
setInterval(pollPackets,3000);
pollPackets();
</script>
</body>
</html>"""



@app.route("/api/packets")
def get_packets():
    import urllib.request
    try:
        bus = os.environ.get("BUS_URL", "http://go-bus:8086")
        req = urllib.request.Request(f"{bus}/api/query?limit=20&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return jsonify({"packets": data if isinstance(data, list) else data.get("events", [])})
    except Exception as e:
        return jsonify({"packets": [], "error": str(e)})

if __name__=="__main__":
    app.run(host="0.0.0.0",port=8090)