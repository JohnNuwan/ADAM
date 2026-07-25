#!/usr/bin/env python3
"""Graphify 3D — Visualisation du knowledge graph ADAM"""
from flask import Flask, jsonify, send_from_directory
import psycopg2, json, os

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:adam_secret_2026@postgres:5432/adam")

@app.route("/api/graph")
def get_graph():
    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()
    nodes = []
    cur.execute("SELECT id, label, name, properties FROM knowledge_nodes LIMIT 500")
    for row in cur:
        nodes.append({"id": str(row[0]), "label": row[1], "name": row[2], "properties": row[3] or {}})
    edges = []
    cur.execute("SELECT source_id, target_id, relation FROM knowledge_edges LIMIT 1000")
    for row in cur:
        edges.append({"source": str(row[0]), "target": str(row[1]), "relation": row[2]})
    cur.close()
    pg.close()
    return jsonify({"nodes": nodes, "edges": edges})

@app.route("/")
def index():
    return """<html><head><title>ADAM Graph — Knowledge Graph 3D</title>
<style>*{margin:0;padding:0;background:#0a0a0f;color:#e0e0e8;font-family:sans-serif}</style></head>
<body><div id="app"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
(async()=>{
const res=await fetch('/api/graph'),data=await res.json();
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(75,window.innerWidth/window.innerHeight,0.1,1000);
const renderer=new THREE.WebGLRenderer({antialias:true});
renderer.setSize(window.innerWidth,window.innerHeight);
document.getElementById('app').appendChild(renderer.domElement);
const controls=new THREE.OrbitControls(camera,renderer.domElement);

// Color mapping
const colors={Agent:0x00ff88,Topic:0x4488ff,Project:0xff8844,Skill:0xff44ff,Concept:0x44ff88};
const nodes={};
data.nodes.forEach((n,i)=>{
    const color=colors[n.label]||0x888888;
    const geom=new THREE.SphereGeometry(n.label==='Agent'?0.5:0.3,16,16);
    const mat=new THREE.MeshPhongMaterial({color});
    const mesh=new THREE.Mesh(geom,mat);
    const angle=(2*Math.PI*i)/data.nodes.length;
    const radius=5+Math.random()*3;
    mesh.position.set(Math.cos(angle)*radius,Math.sin(angle)*radius*0.6,Math.sin(angle*2)*1.5);
    scene.add(mesh);
    nodes[n.id]=mesh;
});

// Edges
data.edges.forEach(e=>{
    if(nodes[e.source]&&nodes[e.target]){
        const pts=[nodes[e.source].position,nodes[e.target].position];
        const geom=new THREE.BufferGeometry().setFromPoints(pts);
        const mat=new THREE.LineBasicMaterial({color:0x446688,transparent:true,opacity:0.4});
        scene.add(new THREE.Line(geom,mat));
    }
});

camera.position.z=12;
const light=new THREE.DirectionalLight(0xffffff,1);light.position.set(10,10,10);scene.add(light);
scene.add(new THREE.AmbientLight(0x222244));
function animate(){requestAnimationFrame(animate);renderer.render(scene,camera)}animate();
window.addEventListener('resize',()=>{camera.aspect=window.innerWidth/window.innerHeight;camera.updateProjectionMatrix();renderer.setSize(window.innerWidth,window.innerHeight)});
})();
</script></body></html>"""

if __name__=="__main__":
    app.run(host="0.0.0.0",port=8090)
