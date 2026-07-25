#!/usr/bin/env python3
"""EVA Activity — Chat feed des agents + Sprint Board"""
from flask import Flask, jsonify, request
import json, os, urllib.request, time, threading
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
BUS_URL = "http://go-bus:8086"
ADAM_DIR = Path("/data/agents")

# Sprint storage (in-memory, could be persisted)
sprints = {}
sprint_counter = 1
lock = threading.Lock()

def poll_activity():
    """Poll Go Bus for all agent activity + auto-create sprints"""
    global activity_log, sprints, sprint_counter
    activity_log = []
    seen_ids = set()
    
    # Auto-create sprints from EVA objectives
    def auto_create_sprints():
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=10&topic=eva:objective")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                events = data if isinstance(data, list) else data.get("events", [])
                for e in events:
                    eid = e.get("id", "")
                    payload = e.get("payload", {})
                    if not isinstance(payload, dict): continue
                    objective = payload.get("objective", "")
                    agents_list = payload.get("agents", [])
                    cycle = payload.get("cycle", 0)
                    
                    # Check if sprint already exists for this objective
                    sprint_id = f"sprint_obj_{cycle}"
                    if sprint_id not in sprints and objective:
                        sprint = {
                            "id": sprint_id,
                            "name": f"Auto-Sprint Cycle {cycle}",
                            "objective": objective,
                            "status": "active",
                            "created_at": datetime.now().isoformat(),
                            "missions": [],
                            "progress": 0
                        }
                        # Add missions for each agent
                        for agent in agents_list:
                            mission = {
                                "id": f"m_{len(sprint['missions'])+1}",
                                "agent": agent if agent.startswith("adam-") else f"adam-{agent}",
                                "mission": objective + " — Ta contribution",
                                "status": "pending",
                                "result": None,
                                "tools_created": [],
                                "timestamp": datetime.now().isoformat()
                            }
                            sprint["missions"].append(mission)
                        with lock:
                            sprints[sprint_id] = sprint
                        print(f"[SPRINT] Auto-created: {sprint_id} — {objective[:60]}")
        except:
            pass
    
    # Auto-clean old completed sprints (keep last 5)
    def cleanup_sprints():
        with lock:
            if len(sprints) > 5:
                # Sort by creation date, keep newest 5
                sorted_ids = sorted(sprints.keys(), key=lambda k: sprints[k].get("created_at", ""))
                for sid in sorted_ids[:-5]:
                    s = sprints[sid]
                    # Only remove if all missions are done or failed
                    all_done = all(m.get("status") in ("done", "failed") for m in s.get("missions", []))
                    if all_done and s.get("missions"):
                        del sprints[sid]
                        print(f"[SPRINT] Cleaned: {sid}")
    
    # Update sprint mission statuses from Go Bus
    def update_sprint_statuses():
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:packet")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                pkts = data if isinstance(data, list) else data.get("events", [])
                with lock:
                    for sid in sprints:
                        s = sprints[sid]
                        for m in s.get("missions", []):
                            # Check if this agent has completed a packet
                            agent_name = m.get("agent", "").lower().replace("adam-", "")
                            for p in pkts:
                                src = p.get("source", "").lower().replace("adam-", "")
                                if src == agent_name:
                                    payload = p.get("payload", {})
                                    if isinstance(payload, dict):
                                        status = payload.get("status", "")
                                        if status == "done":
                                            m["status"] = "done"
                                        elif status == "failed":
                                            m["status"] = "failed"
                                        elif status == "timeout":
                                            m["status"] = "failed"
                                        m["tools_created"] = payload.get("tools_created", [])
                                        m["result"] = payload.get("thought", "")[:100]
                        # Update progress
                        total = len(s.get("missions", []))
                        done = len([m for m in s.get("missions", []) if m.get("status") == "done"])
                        s["progress"] = round(done/total*100) if total > 0 else 0
                        if s["progress"] == 100 and s["status"] != "done":
                            s["status"] = "done"
        except:
            pass
    
    # Run auto-sprint management every 15 seconds
    last_sprint_check = 0
    while True:
        try:
            # Get all recent events (multiple topics)
            topics = ["adam:packet", "adam:mission", "adam:mission:done", "adam:heartbeat", "eva:objective"]
            for topic in topics:
                try:
                    req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic={topic}")
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        data = json.loads(resp.read().decode())
                        events = data if isinstance(data, list) else data.get("events", [])
                        for e in events:
                            eid = e.get("id", "")
                            if eid and eid not in seen_ids:
                                seen_ids.add(eid)
                                with lock:
                                    activity_log.append({
                                        "id": eid,
                                        "source": e.get("source", ""),
                                        "topic": e.get("topic", ""),
                                        "payload": e.get("payload", {}),
                                        "timestamp": e.get("timestamp", ""),
                                        "type": classify_event(e)
                                    })
                    # Keep last 200
                    if len(activity_log) > 200:
                        activity_log[:] = activity_log[-200:]
                except:
                    pass
        except:
            pass
        # Auto-sprint management every 15 seconds
        if time.time() - last_sprint_check > 15:
            auto_create_sprints()
            update_sprint_statuses()
            cleanup_sprints()
            last_sprint_check = time.time()
        
        time.sleep(3)

def classify_event(e):
    """Classify event type for display"""
    topic = e.get("topic", "")
    payload = e.get("payload", {})
    if not isinstance(payload, dict): payload = {}
    
    if "objective" in topic:
        return "objective"
    elif "mission:done" in topic:
        return "mission_done"
    elif "mission" in topic:
        return "mission"
    elif "packet" in topic:
        return "packet"
    elif "heartbeat" in topic:
        return "heartbeat"
    return "event"

threading.Thread(target=poll_activity, daemon=True).start()

@app.route("/api/feed")
def api_feed():
    """Get activity feed (chat-like)"""
    with lock:
        feed = sorted(activity_log, key=lambda x: x.get("timestamp", ""), reverse=True)
    return jsonify({"feed": feed[:50]})

@app.route("/api/sprints")
def api_sprints():
    """Get all sprints"""
    with lock:
        return jsonify({"sprints": list(sprints.values())})

@app.route("/api/sprints", methods=["POST"])
def create_sprint():
    """Create a new sprint"""
    global sprint_counter
    data = request.json
    sprint_id = f"sprint_{sprint_counter}"
    sprint_counter += 1
    sprint = {
        "id": sprint_id,
        "name": data.get("name", f"Sprint {sprint_counter}"),
        "objective": data.get("objective", ""),
        "status": "planning",
        "created_at": datetime.now().isoformat(),
        "missions": [],
        "progress": 0
    }
    with lock:
        sprints[sprint_id] = sprint
    return jsonify(sprint)

@app.route("/api/sprints/<sprint_id>/missions", methods=["POST"])
def add_sprint_mission(sprint_id):
    """Add a mission to a sprint"""
    data = request.json
    with lock:
        if sprint_id not in sprints:
            return jsonify({"error": "sprint not found"}), 404
        mission = {
            "id": f"m_{len(sprints[sprint_id]['missions'])+1}",
            "agent": data.get("agent", ""),
            "mission": data.get("mission", ""),
            "status": "pending",
            "result": None,
            "tools_created": [],
            "timestamp": datetime.now().isoformat()
        }
        sprints[sprint_id]["missions"].append(mission)
        # Publish to Go Bus
        try:
            payload = json.dumps({
                "topic": "adam:mission",
                "source": f"sprint_{sprint_id}",
                "payload": {"agent": mission["agent"], "mission": mission["mission"], "status": "pending", "sprint": sprint_id},
                "priority": 2
            }).encode()
            req = urllib.request.Request(f"{BUS_URL}/api/publish", data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3)
        except:
            pass
    return jsonify(mission)

@app.route("/api/sprints/<sprint_id>", methods=["PUT"])
def update_sprint(sprint_id):
    """Update sprint status"""
    data = request.json
    with lock:
        if sprint_id not in sprints:
            return jsonify({"error": "sprint not found"}), 404
        if "status" in data:
            sprints[sprint_id]["status"] = data["status"]
        if "progress" in data:
            sprints[sprint_id]["progress"] = data["progress"]
    return jsonify(sprints[sprint_id])

@app.route("/api/agents/detail")
def api_agents_detail():
    """Get detailed agent status with current mission, tools, memory"""
    try:
        # Get packets for current status
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
                    "current_mission": payload.get("mission", "")[:80],
                    "thought": payload.get("thought", "")[:120],
                    "status": payload.get("status", ""),
                    "tools_created": payload.get("tools_created", []),
                    "timestamp": p.get("timestamp", "")
                }
        
        # Add memory stats
        if ADAM_DIR.exists():
            for d in sorted(ADAM_DIR.iterdir()):
                if d.is_dir():
                    name = "adam-" + d.name
                    mdir = d / "memory"
                    if mdir.exists() and name in agents:
                        mf = mdir / "missions.json"
                        lf = mdir / "lessons.json"
                        try:
                            mdata = json.loads(mf.read_text())
                            agents[name]["total_missions"] = len(mdata.get("missions", []))
                        except: agents[name]["total_missions"] = 0
                        try:
                            ldata = json.loads(lf.read_text())
                            agents[name]["total_lessons"] = len(ldata.get("lessons", []))
                        except: agents[name]["total_lessons"] = 0
        
        return jsonify({"agents": agents})
    except Exception as e:
        return jsonify({"agents": {}, "error": str(e)})

HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EVA Activity — Feed & Sprints</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0a14;color:#e0e8f0;font-family:'SF Pro Display','Segoe UI',system-ui,sans-serif}
.layout{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:44px 1fr;height:100vh;gap:1px}

/* Top bar */
#topbar{grid-column:1/3;display:flex;align-items:center;justify-content:space-between;padding:0 20px;background:rgba(5,5,16,0.95);border-bottom:1px solid rgba(68,102,136,0.1)}
#topbar .title{font-size:14px;font-weight:700;background:linear-gradient(90deg,#00aaff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
#topbar .nav{display:flex;gap:8px}
#topbar .nav button{background:rgba(68,102,136,0.1);border:1px solid rgba(68,102,136,0.2);border-radius:6px;padding:5px 12px;color:#88aacc;font-size:11px;cursor:pointer}
#topbar .nav button:hover{background:rgba(0,170,255,0.15);color:#00aaff}

/* Panels */
.panel{background:rgba(5,5,16,0.9);overflow:hidden;display:flex;flex-direction:column}
.panel-header{padding:10px 14px;border-bottom:1px solid rgba(68,102,136,0.1);display:flex;align-items:center;justify-content:space-between}
.panel-header h2{font-size:11px;color:#5577aa;text-transform:uppercase;letter-spacing:0.5px;display:flex;align-items:center;gap:6px}
.panel-header .dot{width:6px;height:6px;border-radius:50%;background:#00ff88;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.3}}
.panel-content{flex:1;overflow-y:auto;padding:10px}
.panel-content::-webkit-scrollbar{width:3px}
.panel-content::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3)}

/* Feed messages */
.feed-msg{padding:8px 10px;margin-bottom:6px;border-radius:8px;background:rgba(10,15,25,0.6);font-size:11px;line-height:1.5;border-left:3px solid #446688;cursor:pointer;transition:background 0.2s}
.feed-msg:hover{background:rgba(10,15,25,0.9)}
.feed-msg .content{max-height:200px;overflow-y:auto}
.feed-msg.objective{border-left-color:#00aaff;background:rgba(0,170,255,0.05)}
.feed-msg.mission{border-left-color:#ffaa44;background:rgba(255,170,68,0.05)}
.feed-msg.mission_done{border-left-color:#00ff88;background:rgba(0,255,136,0.05)}
.feed-msg.packet{border-left-color:#446688}
.feed-msg .header{display:flex;justify-content:space-between;margin-bottom:3px}
.feed-msg .agent{font-weight:600;color:#00ff88;font-size:10px}
.feed-msg .time{font-size:9px;color:#446688}
.feed-msg .content{color:#88aacc;word-wrap:break-word;white-space:pre-wrap;line-height:1.5}
.feed-msg .content .mission-full{color:#e0e8f0;font-weight:500}
.feed-msg .content .thought-full{color:#88aacc;font-style:italic}
.feed-msg .content .output-full{color:#6688aa;font-family:monospace;font-size:10px}
.feed-msg .tools{color:#ffaa00;font-size:10px;margin-top:2px}
.feed-msg .status{font-size:9px;padding:1px 6px;border-radius:6px;display:inline-block;margin-top:2px}
.feed-msg .status.done{background:#00ff8822;color:#00ff88}
.feed-msg .status.failed{background:#ff446622;color:#ff4466}
.feed-msg .status.timeout{background:#ffaa4422;color:#ffaa44}
.feed-msg .status.pending{background:#44668822;color:#88aacc}

/* Agent cards */
.agent-card{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #00ff88}
.agent-card .name{font-size:12px;font-weight:600;color:#00ff88;margin-bottom:4px}
.agent-card .mission{font-size:11px;color:#e0e8f0;margin-bottom:4px;word-wrap:break-word;white-space:pre-wrap;line-height:1.4}
.agent-card .thought{font-size:10px;color:#88aacc;font-style:italic;margin-bottom:4px;word-wrap:break-word;white-space:pre-wrap;line-height:1.4}
.agent-card .stats{font-size:9px;color:#5577aa;display:flex;gap:12px}
.agent-card .stats .stat{display:flex;gap:3px}
.agent-card .stats .stat .v{color:#00aaff;font-weight:600}
.agent-card .progress{height:3px;background:rgba(68,102,136,0.2);border-radius:2px;margin-top:6px;overflow:hidden}
.agent-card .progress-fill{height:100%;background:linear-gradient(90deg,#00aaff,#00ff88);border-radius:2px;transition:width 0.3s}

/* Sprint board */
.sprint{background:rgba(10,15,25,0.6);border-radius:8px;padding:12px;margin-bottom:12px;border:1px solid rgba(68,102,136,0.15)}
.sprint-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.sprint-name{font-size:13px;font-weight:600;color:#00aaff}
.sprint-status{font-size:9px;padding:2px 8px;border-radius:6px}
.sprint-status.planning{background:#ffaa4422;color:#ffaa44}
.sprint-status.active{background:#00ff8822;color:#00ff88}
.sprint-status.done{background:#44668822;color:#446688}
.sprint-objective{font-size:10px;color:#88aacc;margin-bottom:8px}
.sprint-progress{height:4px;background:rgba(68,102,136,0.2);border-radius:2px;margin-bottom:8px;overflow:hidden}
.sprint-progress-fill{height:100%;background:linear-gradient(90deg,#00aaff,#00ff88);border-radius:2px}
.sprint-missions{display:flex;flex-direction:column;gap:4px}
.sprint-mission{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:10px;border-bottom:1px solid rgba(68,102,136,0.06)}
.sprint-mission .status-dot{width:8px;height:8px;border-radius:50%;min-width:8px}
.sprint-mission .status-dot.pending{background:#ffaa44}
.sprint-mission .status-dot.running{background:#00aaff;animation:pulse 1s infinite}
.sprint-mission .status-dot.done{background:#00ff88}
.sprint-mission .status-dot.failed{background:#ff4466}
.sprint-mission .agent{color:#00ff88;font-weight:600;min-width:70px}
.sprint-mission .text{color:#88aacc;flex:1;word-wrap:break-word;white-space:pre-wrap;line-height:1.3;font-size:10px}

/* New sprint button */
.btn-new{background:#00aaff33;border:1px solid #00aaff44;color:#00aaff;border-radius:6px;padding:6px 12px;font-size:11px;cursor:pointer}
.btn-new:hover{background:#00aaff22}

/* Modal */
.modal-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);display:none;align-items:center;justify-content:center;z-index:1000}
.modal-overlay.visible{display:flex}
.modal{background:#0a0a14;border:1px solid rgba(68,102,136,0.2);border-radius:12px;padding:20px;width:400px}
.modal h3{font-size:14px;margin-bottom:12px;color:#00aaff}
.modal input,.modal textarea{width:100%;background:rgba(10,15,25,0.6);border:1px solid rgba(68,102,136,0.2);border-radius:6px;padding:8px;color:#e0e8f0;font-size:11px;margin-bottom:8px}
.modal button{background:#00aaff;border:none;border-radius:6px;padding:8px 16px;color:#fff;font-size:11px;cursor:pointer;margin-right:8px}
.modal button.cancel{background:rgba(68,102,136,0.2)}

/* Mission columns */
.mission-cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:8px}
.mission-col{background:rgba(5,5,16,0.5);border-radius:6px;padding:6px}
.mission-col h4{font-size:9px;color:#5577aa;text-transform:uppercase;margin-bottom:4px}
</style>
</head>
<body>
<div class="layout">
  <div id="topbar">
    <div class="title">EVA Activity</div>
    <div class="nav">
      <button onclick="fetchFeed()">Refresh</button>
      <button onclick="showNewSprint()">+ Sprint</button>
    </div>
  </div>

  <!-- Left: Activity Feed -->
  <div class="panel">
    <div class="panel-header">
      <h2><span class="dot"></span>Activity Feed — EVA & Adams</h2>
    </div>
    <div class="panel-content" id="feed-content"></div>
  </div>

  <!-- Right: Sprints + Agents -->
  <div class="panel" style="overflow-y:auto">
    <div class="panel-header">
      <h2><span class="dot"></span>Sprints & Agents</h2>
    </div>
    <div class="panel-content">
      <!-- Agent status -->
      <div id="agents-detail"></div>
      <!-- Sprint board -->
      <div id="sprints-board" style="margin-top:12px"></div>
    </div>
  </div>
</div>

<!-- New Sprint Modal -->
<div class="modal-overlay" id="sprint-modal">
  <div class="modal">
    <h3>Nouveau Sprint</h3>
    <input type="text" id="sprint-name" placeholder="Nom du sprint (ex: Sprint Sécurité)">
    <input type="text" id="sprint-obj" placeholder="Objectif (ex: Améliorer la sécurité du serveur)">
    <div id="sprint-missions-container"></div>
    <button onclick="addMissionField()">+ Mission</button>
    <div style="margin-top:12px">
      <button onclick="createSprint()">Créer</button>
      <button class="cancel" onclick="hideNewSprint()">Annuler</button>
    </div>
  </div>
</div>

<script>
var missionFields = [];

function fetchFeed() {
  fetch('/api/feed').then(r=>r.json()).then(d=>{
    var el = document.getElementById('feed-content');
    var feed = d.feed || [];
    var html = '';
    for (var i=0; i<Math.min(feed.length,40); i++) {
      var f = feed[i];
      var t = (f.timestamp||'').slice(11,19) || '--:--:--';
      var date = (f.timestamp||'').slice(0,10);
      var payload = f.payload || {};
      if (!typeof payload === 'object') payload = {};
      var agent = f.source || '';
      var type = f.type || 'event';
      var content = '';
      var tools = '';
      var status = '';
      
      if (payload.mission) content = payload.mission;
      else if (payload.thought) content = payload.thought;
      else if (payload.output) content = payload.output.substring(0,200);
      else if (payload.objective) content = payload.objective;
      else if (payload.cycle !== undefined) content = 'Cycle ' + payload.cycle + ' — ' + (payload.agents||'') + ' agents';
      else content = JSON.stringify(payload).substring(0,150);
      
      if (payload.tools_created && payload.tools_created.length) {
        tools = '🔧 ' + payload.tools_created.join(', ');
      }
      if (payload.status) {
        status = '<div class="status '+payload.status+'">'+payload.status+'</div>';
      }
      
      var agentDisplay = agent.replace('adam-','').replace('eva-','EVA: ');
      if (agent === 'daemon') agentDisplay = '⚙️ Daemon';
      if (agent === 'eva-commander' || agent === 'eva-chat') agentDisplay = '🐝 EVA';
      
      html += '<div class="feed-msg '+type+'">';
      html += '<div class="header"><span class="agent">'+agentDisplay+'</span><span class="time">'+date+' '+t+'</span></div>';
      html += '<div class="content">'+content+'</div>';
      if (tools) html += '<div class="tools">'+tools+'</div>';
      if (status) html += status;
      html += '</div>';
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px;padding:20px">En attente d\'activité...</div>';
    el.innerHTML = html;
  });
}

function fetchAgentsDetail() {
  fetch('/api/agents/detail').then(r=>r.json()).then(d=>{
    var el = document.getElementById('agents-detail');
    var agents = d.agents || {};
    var keys = Object.keys(agents).sort();
    var html = '';
    for (var i=0; i<keys.length; i++) {
      var a = agents[keys[i]];
      var name = keys[i].replace('adam-','');
      var t = (a.timestamp||'').slice(11,19) || '--:--:--';
      var st = a.status || 'done';
      var stColor = st==='done'?'#00ff88':(st==='failed'?'#ff4466':(st==='timeout'?'#ffaa44':'#00aaff'));
      var pct = st==='done'?100:(st==='failed'?100:50);
      var tools = a.tools_created || [];
      var totalM = a.total_missions || 0;
      var totalL = a.total_lessons || 0;
      
      html += '<div class="agent-card" style="border-left-color:'+stColor+'">';
      html += '<div class="name">'+name+' <span style="font-size:9px;color:#446688">('+t+')</span></div>';
      if (a.current_mission) html += '<div class="mission">📋 '+a.current_mission+'</div>';
      if (a.thought) html += '<div class="thought">💭 '+a.thought+'</div>';
      if (tools.length) html += '<div style="font-size:9px;color:#ffaa00;margin-top:2px">🔧 '+tools.join(', ').substring(0,50)+'</div>';
      html += '<div class="stats">';
      html += '<div class="stat">Missions: <span class="v">'+totalM+'</span></div>';
      html += '<div class="stat">Leçons: <span class="v">'+totalL+'</span></div>';
      html += '<div class="stat">Statut: <span class="v" style="color:'+stColor+'">'+st+'</span></div>';
      html += '</div>';
      html += '<div class="progress"><div class="progress-fill" style="width:'+pct+'%;background:'+stColor+'"></div></div>';
      html += '</div>';
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px;padding:10px">Aucun agent actif</div>';
    el.innerHTML = html;
  });
}

function fetchSprints() {
  fetch('/api/sprints').then(r=>r.json()).then(d=>{
    var el = document.getElementById('sprints-board');
    var sprints = d.sprints || [];
    var html = '';
    for (var i=0; i<sprints.length; i++) {
      var s = sprints[i];
      var totalM = s.missions.length;
      var doneM = s.missions.filter(m=>m.status==='done').length;
      var pct = totalM > 0 ? Math.round(doneM/totalM*100) : 0;
      
      html += '<div class="sprint">';
      html += '<div class="sprint-header">';
      html += '<div class="sprint-name">'+s.name+'</div>';
      html += '<div class="sprint-status '+s.status+'">'+s.status.toUpperCase()+'</div>';
      html += '</div>';
      html += '<div class="sprint-objective">🎯 '+s.objective+'</div>';
      html += '<div class="sprint-progress"><div class="sprint-progress-fill" style="width:'+pct+'%"></div></div>';
      html += '<div style="font-size:9px;color:#5577aa;margin-bottom:6px">'+doneM+'/'+totalM+' missions — '+pct+'%</div>';
      
      // Mission columns
      var pending = s.missions.filter(m=>m.status==='pending');
      var running = s.missions.filter(m=>m.status==='running' || (m.status!=='done' && m.status!=='failed' && m.status!=='pending'));
      var done = s.missions.filter(m=>m.status==='done' || m.status==='failed');
      
      html += '<div class="mission-cols">';
      html += '<div class="mission-col"><h4>À faire ('+pending.length+')</h4>';
      for (var j=0; j<pending.length; j++) {
        html += '<div class="sprint-mission"><div class="status-dot pending"></div><div class="agent">'+pending[j].agent.replace('adam-','')+'</div><div class="text">'+pending[j].mission+'</div></div>';
      }
      html += '</div>';
      html += '<div class="mission-col"><h4>En cours ('+running.length+')</h4>';
      for (var j=0; j<running.length; j++) {
        html += '<div class="sprint-mission"><div class="status-dot running"></div><div class="agent">'+running[j].agent.replace('adam-','')+'</div><div class="text">'+running[j].mission+'</div></div>';
      }
      html += '</div>';
      html += '<div class="mission-col"><h4>Terminé ('+done.length+')</h4>';
      for (var j=0; j<done.length; j++) {
        var stColor = done[j].status==='done'?'done':'failed';
        html += '<div class="sprint-mission"><div class="status-dot '+stColor+'"></div><div class="agent">'+done[j].agent.replace('adam-','')+'</div><div class="text">'+done[j].mission+'</div></div>';
      }
      html += '</div>';
      html += '</div>';
      html += '</div>';
    }
    if (!html) html = '<div style="color:#5577aa;font-size:11px;padding:10px">Aucun sprint. Clique sur "+ Sprint" pour en créer un.</div>';
    el.innerHTML = html;
  });
}

// Sprint creation
function showNewSprint() {
  document.getElementById('sprint-modal').classList.add('visible');
  missionFields = [];
  document.getElementById('sprint-missions-container').innerHTML = '';
  addMissionField();
}
function hideNewSprint() {
  document.getElementById('sprint-modal').classList.remove('visible');
}
function addMissionField() {
  var container = document.getElementById('sprint-missions-container');
  var idx = missionFields.length;
  var div = document.createElement('div');
  div.style.marginTop = '8px';
  div.innerHTML = '<input type="text" placeholder="Agent (ex: adam-sentinel)" style="width:45%" id="mf-agent-'+idx+'">' +
                   '<input type="text" placeholder="Mission" style="width:54%" id="mf-mission-'+idx+'">';
  container.appendChild(div);
  missionFields.push(idx);
}
function createSprint() {
  var name = document.getElementById('sprint-name').value || 'Sprint ' + Date.now();
  var obj = document.getElementById('sprint-obj').value || '';
  
  fetch('/api/sprints', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: name, objective: obj})
  }).then(r=>r.json()).then(sprint=>{
    // Add missions
    var promises = [];
    for (var i=0; i<missionFields.length; i++) {
      var agent = document.getElementById('mf-agent-'+i).value;
      var mission = document.getElementById('mf-mission-'+i).value;
      if (agent && mission) {
        promises.push(fetch('/api/sprints/'+sprint.id+'/missions', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({agent: agent, mission: mission})
        }));
      }
    }
    Promise.all(promises).then(()=>{
      hideNewSprint();
      fetchSprints();
    });
  });
}

// Start
fetchFeed();
fetchAgentsDetail();
fetchSprints();
setInterval(fetchFeed, 3000);
setInterval(fetchAgentsDetail, 5000);
setInterval(fetchSprints, 10000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8092)
