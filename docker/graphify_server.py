#!/usr/bin/env python3
"""Graphify V8 — Clean Hub + Panel System (draggable/collapsible)"""
from flask import Flask, jsonify, request
import psycopg2, json, os, urllib.request, time, threading
from collections import defaultdict

app = Flask(__name__)
PG_DSN = os.environ.get("PG_DSN", "postgres://adam:***@postgres:5432/adam")
BUS_URL = os.environ.get("BUS_URL", "http://go-bus:8086")
VLLM_URL = os.environ.get("VLLM_URL", "http://192.168.1.5:8000")

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
            hub = {"eva": None, "agents": [], "skills": [], "services": [], "edges": edges}
            for n in nodes:
                if n["label"] == "EVA": hub["eva"] = n
                elif n["label"] == "Agent": hub["agents"].append(n)
                elif n["label"] == "SkillDomain": hub["skills"].append(n)
                elif n["label"] == "Service": hub["services"].append(n)

            # Auto-detect new agents from filesystem (AGI-3 created agents)
            try:
                from pathlib import Path as _P
                agents_fs = _P("/data/agents")
                if agents_fs.exists():
                    existing_names = {a["name"].lower().replace("adam-","") for a in hub["agents"]}
                    for d in sorted(agents_fs.iterdir()):
                        if d.is_dir() and d.name.lower() not in existing_names and d.name not in ["new"]:
                            import uuid as _uuid
                            uid = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, f"adam-{d.name}"))
                            # Add to PG
                            try:
                                cur2 = pg.cursor()
                                cur2.execute("INSERT INTO knowledge_nodes (id, label, name, properties) VALUES (%s, 'Agent', %s, %s) ON CONFLICT DO NOTHING",
                                           (uid, f"Adam-{d.name.title()}", json.dumps({"role": "Agent créé", "workspace": d.name})))
                                pg.commit()
                                cur2.close()
                            except:
                                pass
                            # Add to hub
                            hub["agents"].append({"id": uid, "label": "Agent", "name": f"Adam-{d.name.title()}", "properties": {"role": "Agent créé"}})
            except:
                pass
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
            # Try multiple possible paths
            candidates = [
                Path("/data/agents"),
                Path("/data/agents"),
                Path("/data/agents"),
            ]
            adir = None
            for p in candidates:
                if p.exists():
                    adir = p
                    break
            new_tools = {}
            if adir:
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
        except Exception as e:
            print(f"[ERR tools] {e}", flush=True)
        time.sleep(30)

threading.Thread(target=refresh_graph, daemon=True).start()
threading.Thread(target=poll_activity, daemon=True).start()
threading.Thread(target=poll_missions, daemon=True).start()
threading.Thread(target=refresh_tools, daemon=True).start()

@app.route("/api/stats")
def api_stats_full():
    """Get real stats including actual SKILL.md count"""
    try:
        import os
        from pathlib import Path
        # Count real SKILL.md files
        skills_count = 0
        skills_paths = [
            Path("/data/agents"),
            Path("/home/aza/eva-adam-v2"),
        ]
        # Also count from EVA_CORE if accessible
        import subprocess as _sp
        try:
            r = _sp.run(["find", "/data/skills", "-name", "SKILL.md"], capture_output=True, text=True, timeout=5)
            skills_count = len([l for l in r.stdout.strip().split("\n") if l.strip()])
        except:
            skills_count = 0
        
        # Count tools
        tools_count = 0
        agents_dir = Path("/data/agents")
        if agents_dir.exists():
            for d in agents_dir.iterdir():
                if d.is_dir():
                    tdir = d / "tools"
                    if tdir.exists():
                        tools_count += len([f for f in tdir.glob("*.py") if "registry" not in f.name and "backup" not in str(f) and "self_improvement" not in f.name])
        
        # Count agents (directories)
        agents_count = len([d for d in agents_dir.iterdir() if d.is_dir()]) if agents_dir.exists() else 0
        
        # Count lessons
        lessons_count = 0
        if agents_dir.exists():
            for d in agents_dir.iterdir():
                if d.is_dir():
                    lf = d / "memory" / "lessons.json"
                    if lf.exists():
                        try:
                            import json as _j
                            lessons_count += len(_j.loads(lf.read_text()).get("lessons", []))
                        except: pass
        
        return jsonify({
            "skills": skills_count,
            "tools": tools_count,
            "agents": agents_count,
            "lessons": lessons_count
        })
    except Exception as e:
        return jsonify({"skills": 0, "tools": 0, "agents": 0, "lessons": 0, "error": str(e)})

@app.route("/api/graph")
def api_graph():
    with lock:
        return jsonify(graph_cache)

@app.route("/api/activity")
def api_activity():
    """Get activity from Go Bus directly"""
    try:
        req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:packet")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            pkts = data if isinstance(data, list) else data.get("events", [])
            # Sort by timestamp desc (newest first)
            pkts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            activity = {}
            for p in pkts:
                src = p.get("source", "")
                if src and src not in activity:  # Only keep latest per agent
                    payload = p.get("payload", {})
                    if not isinstance(payload, dict):
                        payload = {}
                    thought = payload.get("thought", "")
                    if not thought:
                        output = payload.get("output", "")
                        thought = output[:100] if output else payload.get("status", "done")
                    mission = payload.get("mission", "")
                    tools = payload.get("tools_created", [])
                    if not mission:
                        # Try to extract from output
                        output = payload.get("output", "")
                        if "mission:" in output.lower():
                            for line in output.split("\n"):
                                if "mission:" in line.lower():
                                    mission = line.split("mission:")[-1].strip()[:80]
                                    break
                    if not thought or thought == "done":
                        if mission:
                            thought = f"Mission: {mission[:60]}"
                            if tools:
                                thought += f" | Outils: {', '.join(tools[:2])}"
                        else:
                            output = payload.get("output", "")
                            thought = output[:100] if output else "En cours..."
                    activity[src] = {
                        "thought": str(thought)[:150],
                        "mission": mission[:100],
                        "tools": tools[:5],
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
        tc = dict(tools_cache)
    # Fallback: if no tools from filesystem, check Go Bus
    if not tc:
        try:
            req = urllib.request.Request(f"{BUS_URL}/api/query?limit=20&topic=adam:tool:created")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                events = data if isinstance(data, list) else data.get("events", [])
                for e in events:
                    src = e.get("source", "")
                    payload = e.get("payload", {})
                    if isinstance(payload, dict) and src:
                        key = "adam-" + src.replace("adam-", "")
                        if key not in tc:
                            tc[key] = {"scripts": [], "tools": []}
                        tool = payload.get("tool", payload.get("name", ""))
                        if tool and tool not in tc[key]["tools"]:
                            tc[key]["tools"].append(tool)
        except:
            pass
    return jsonify({"tools": tc})

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

def _call_qwen(system_prompt, user_msg, max_tokens=512, temperature=0.3):
    """Call Qwen VLLM and return the text response."""
    payload = json.dumps({
        "model": "Qwen2.5-32B-Instruct-AWQ",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }).encode()
    req = urllib.request.Request(f"{VLLM_URL}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
        return data["choices"][0]["message"]["content"]


def _publish_to_bus(topic, source, payload_dict, priority=2):
    """Publish a message to the Go Bus."""
    body = json.dumps({"topic": topic, "source": source, "payload": payload_dict, "priority": priority}).encode()
    req = urllib.request.Request(f"{BUS_URL}/api/publish", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def _parse_json_response(raw):
    """Try to parse JSON from Qwen response, handling markdown and extra text."""
    raw = raw.strip()
    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try extracting from markdown code block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding first {...} block
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


@app.route("/api/eva/chat", methods=["POST"])
def eva_chat():
    msg = request.json.get("message", "")
    if not msg:
        return jsonify({"error": "no message"})

    # Gather system state for context
    with lock:
        hub = graph_cache.get("hub") or {}
        agents = [a.get("name", str(a.get("id", ""))) for a in hub.get("agents", [])]
        missions_snapshot = list(missions_cache)

    agent_list = ", ".join(agents) if agents else "aucun agent enregistre"

    # Phase 1: Classify the message with Qwen
    classify_system = (
        "Tu es EVA, l'orchestrateur intelligent du systeme ADAM. "
        f"Tu controles {len(agents)} agents: {agent_list}. "
        "Analyse la demande de l'utilisateur et classifie-la. "
        "Reponds UNIQUEMENT avec un objet JSON valide, sans texte supplementaire.\n"
        "Types possibles:\n"
        '1. Objectif a decomposer: {"type":"objective","objective":"<description de l objectif>"}\n'
        '2. Mission directe pour un agent: {"type":"mission","agent":"<nom de l agent>","mission":"<description de la mission>"}\n'
        '3. Question sur l etat du systeme: {"type":"question"}\n'
        "Regles:\n"
        "- Si la demande est un grand objectif qui necessite plusieurs agents ou etapes, utilise 'objective'\n"
        "- Si la demande cible un agent specifique ou une tache precise pour un agent, utilise 'mission' avec le nom exact de l'agent\n"
        "- Si c'est une question sur l'etat, les performances, ou une demande d'information, utilise 'question'\n"
        f"- Les noms d'agents disponibles sont: {agent_list}"
    )

    try:
        raw_classify = _call_qwen(classify_system, msg, max_tokens=256, temperature=0.2)
    except Exception as e:
        return jsonify({"response": f"Erreur LLM (classification): {e}", "model": "error"})

    classification = _parse_json_response(raw_classify)
    if not classification or "type" not in classification:
        classification = {"type": "question"}

    msg_type = classification.get("type", "question")

    # Phase 2: Act based on classification
    if msg_type == "objective":
        objective = classification.get("objective", msg)
        # Decompose objective into individual missions using Qwen
        decompose_system = (
            "Tu es EVA, l'orchestrateur du systeme ADAM. "
            f"Tu controles {len(agents)} agents: {agent_list}. "
            "Decompose l'objectif en missions concretes pour les agents. "
            "Reponds UNIQUEMENT avec un objet JSON valide: "
            '{"missions": [{"agent": "<nom exact de l agent>", "mission": "<description claire de la mission>", "priority": 1-3}]}'
            "\nRegles:\n"
            "- Utilise uniquement les noms d'agents disponibles\n"
            "- Chaque mission doit etre actionnable et concrete\n"
            "- 1 a 5 missions maximum\n"
            f"- Agents disponibles: {agent_list}"
        )
        try:
            raw_decompose = _call_qwen(decompose_system, objective, max_tokens=512, temperature=0.3)
        except Exception as e:
            return jsonify({"response": f"Erreur LLM (decomposition): {e}", "model": "error"})

        decomp = _parse_json_response(raw_decompose)
        missions_list = []
        if decomp and "missions" in decomp:
            missions_list = decomp["missions"]

        if not missions_list:
            # Fallback: publish as single objective
            try:
                _publish_to_bus("eva:objective", "eva-chat", {"objective": objective, "source": "eva-chat"})
            except Exception:
                pass
            return jsonify({
                "response": f"Objectif publie: \"{objective}\" (decomposition non disponible, objectif envoye tel quel)",
                "model": "Qwen2.5-32B",
                "action": {"type": "objective", "topic": "eva:objective", "objective": objective}
            })

        # Publish each mission to adam:mission on the Go Bus
        published = []
        failed = []
        for m in missions_list:
            agent = m.get("agent", agents[0] if agents else "adam-recon")
            mission = m.get("mission", "")
            priority = m.get("priority", 2)
            try:
                _publish_to_bus("adam:mission", "eva-chat",
                                {"agent": agent, "mission": mission, "status": "pending", "objective": objective},
                                priority=priority)
                published.append({"agent": agent, "mission": mission})
            except Exception as e:
                failed.append({"agent": agent, "mission": mission, "error": str(e)})

        # Also publish the objective itself for logging
        try:
            _publish_to_bus("eva:objective", "eva-chat",
                            {"objective": objective, "missions_count": len(published), "source": "eva-chat"})
        except Exception:
            pass

        summary = f"Objectif: \"{objective}\"\n\n{len(published)} mission(s) envoyee(s) aux agents:"
        for p in published:
            summary += f"\n  - {p['agent']}: {p['mission']}"
        if failed:
            summary += f"\n\n{len(failed)} echec(s):"
            for f2 in failed:
                summary += f"\n  - {f2['agent']}: {f2['error']}"

        return jsonify({
            "response": summary,
            "model": "Qwen2.5-32B",
            "action": {"type": "objective", "objective": objective, "missions": published, "failed": failed}
        })

    elif msg_type == "mission":
        agent = classification.get("agent", agents[0] if agents else "adam-recon")
        mission = classification.get("mission", msg)
        try:
            _publish_to_bus("adam:mission", "eva-chat", {"agent": agent, "mission": mission, "status": "pending"})
            return jsonify({
                "response": f"Mission envoyee a {agent}: \"{mission}\"\nL'agent va traiter cette mission des que possible.",
                "model": "Qwen2.5-32B",
                "action": {"type": "mission", "topic": "adam:mission", "agent": agent, "mission": mission}
            })
        except Exception as e:
            return jsonify({
                "response": f"Mission identifiee mais erreur de publication sur le Go Bus: {e}",
                "model": "error",
                "action": {"type": "mission", "agent": agent, "mission": mission, "error": str(e)}
            })

    else:  # question
        # Build context about system state
        running_missions = []
        pending_missions = []
        for m in missions_snapshot:
            p = m.get("payload", {}) if isinstance(m.get("payload"), dict) else {}
            status = p.get("status", "unknown")
            mission_text = p.get("mission", p.get("objective", ""))
            src = m.get("source", "")
            if status == "running":
                running_missions.append(f"  - {src}: {mission_text}")
            elif status == "pending":
                pending_missions.append(f"  - {src}: {mission_text}")

        context = (
            f"Etat du systeme ADAM:\n"
            f"- Agents actifs: {len(agents)} ({agent_list})\n"
            f"- Missions totales sur le bus: {len(missions_snapshot)}\n"
            f"- Missions en cours: {len(running_missions)}\n"
            f"- Missions en attente: {len(pending_missions)}\n"
        )
        if running_missions:
            context += "Missions running:\n" + "\n".join(running_missions) + "\n"
        if pending_missions:
            context += "Missions pending:\n" + "\n".join(pending_missions) + "\n"

        answer_system = (
            "Tu es EVA, l'orchestrateur du systeme ADAM. "
            "Tu reponds en francais, de maniere concise et utile. "
            "Voici l'etat actuel du systeme:\n\n" + context
        )

        try:
            answer = _call_qwen(answer_system, msg, max_tokens=512, temperature=0.5)
            return jsonify({"response": answer, "model": "Qwen2.5-32B", "action": {"type": "question"}})
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
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
body{background:#050510;color:#e0e8f0;font-family:'Inter',system-ui,sans-serif;overflow:hidden}
#topbar{position:fixed;top:0;left:0;right:0;height:50px;background:rgba(5,5,16,0.85);backdrop-filter:blur(20px) saturate(180%);display:flex;align-items:center;justify-content:space-between;padding:0 24px;z-index:1000;border-bottom:1px solid rgba(0,170,255,0.08);box-shadow:0 1px 20px rgba(0,0,0,0.5)}
#topbar .logo{display:flex;align-items:center;gap:10px}
#topbar .logo .dot{width:8px;height:8px;border-radius:50%;background:#00aaff;box-shadow:0 0 12px #00aaff;animation:pulse 2s infinite}
#topbar .logo span{font-size:14px;font-weight:700;letter-spacing:-0.3px;background:linear-gradient(135deg,#00aaff,#00ff88);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
#topbar .stats{display:flex;gap:16px;font-size:11px;color:#5577aa}
#topbar .stats .val{color:#00aaff;font-weight:700;font-size:13px}
#topbar .nav{display:flex;gap:8px}
#topbar .nav button{background:rgba(0,170,255,0.06);border:1px solid rgba(0,170,255,0.12);border-radius:8px;padding:6px 14px;color:#88aacc;font-size:11px;font-weight:500;cursor:pointer;transition:all 0.3s cubic-bezier(0.4,0,0.2,1)}
#topbar .nav button:hover{background:rgba(0,170,255,0.12);color:#00aaff;border-color:rgba(0,170,255,0.3);transform:translateY(-1px)}
#topbar .nav button:active{transform:translateY(0)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}

#workspace{position:fixed;top:44px;left:0;right:0;bottom:0;display:flex}
#canvas-area{flex:1;position:relative;background:#050510}
#canvas-area canvas{display:block}

.panel{position:absolute;background:rgba(8,8,20,0.75);border:1px solid rgba(255,255,255,0.06);border-radius:16px;display:flex;flex-direction:column;min-width:280px;max-width:380px;box-shadow:0 8px 40px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.04);backdrop-filter:blur(24px) saturate(180%);z-index:100;transition:all 0.3s cubic-bezier(0.4,0,0.2,1)}
.panel-header{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.04);cursor:move;user-select:none}
.panel-header h3{font-size:10px;color:#6688aa;text-transform:uppercase;letter-spacing:1px;font-weight:600;display:flex;align-items:center;gap:6px}
.panel-header .live{width:5px;height:5px;border-radius:50%;background:#ff4466;animation:pulse 1s infinite}
.panel-header .controls{display:flex;gap:4px}
.panel-header .controls button{background:none;border:none;color:#446688;font-size:14px;cursor:pointer;padding:4px 8px;border-radius:6px;transition:all 0.2s;line-height:1}
.panel-header .controls button:hover{color:#e8e8f0;background:rgba(68,102,136,0.1)}
.panel-content{flex:1;overflow-y:auto;padding:10px;min-height:100px;max-height:400px}
.panel-content::-webkit-scrollbar{width:3px}
.panel-content::-webkit-scrollbar-thumb{background:rgba(68,102,136,0.3);border-radius:2px}
.panel.collapsed .panel-content{display:none}
.panel.collapsed{max-height:44px}
.panel.minimized{max-height:44px;min-height:44px;overflow:hidden}
.panel.minimized .panel-content{display:none}
.panel.minimized .panel-header{cursor:pointer}

#panel-agents{top:20px;left:20px;width:300px}
#panel-missions{bottom:20px;left:20px;width:340px;max-height:300px}
#panel-chat{bottom:20px;right:20px;width:380px;max-height:400px}
#panel-flow{top:20px;right:20px;width:340px;max-height:350px}

.card{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;margin-bottom:8px;border-left:3px solid #00ff88;transition:transform 0.2s}
.card:hover{transform:translateX(2px)}
.card.inactive{border-left-color:#446688}
.card .name{font-size:12px;font-weight:600;color:#00ff88;margin-bottom:4px}
.card .role{font-size:10px;color:#6688aa;margin-bottom:4px}
.card .thought{font-size:10px;color:#88aacc;font-style:italic;line-height:1.4;padding:6px;background:rgba(68,102,136,0.08);border-radius:4px;margin-top:6px}
.card .thought .time{font-size:9px;color:#446688;margin-right:6px}
.card .tools-list{font-size:9px;color:#5577aa;margin-top:6px;padding-top:6px;border-top:1px solid rgba(68,102,136,0.1)}
.card .tools-list .t{color:#00ff88;font-family:monospace}

.mission-card{background:rgba(15,20,35,0.5);border-radius:10px;padding:12px;margin-bottom:8px;border-left:3px solid #00aaff}
.mission-card.running{border-left-color:#00ff88}
.mission-card.done{border-left-color:#446688}
.mission-card .objective{font-size:11px;font-weight:500;color:#e8e8f0;margin-bottom:4px}
.mission-card .agent{font-size:10px;color:#00aaff}
.mission-card .status{font-size:9px;padding:2px 8px;border-radius:8px;display:inline-block;margin-top:4px;font-weight:600}
.mission-card .status.pending{background:#ffaa4422;color:#ffaa44}
.mission-card .status.running{background:#00ff8822;color:#00ff88}
.mission-card .status.done{background:#44668822;color:#446688}

#chat-messages{display:flex;flex-direction:column;gap:8px;padding:10px}
.chat-msg{background:rgba(10,15,25,0.6);border-radius:8px;padding:10px;max-width:85%;font-size:11px;line-height:1.5}
.chat-msg.user{align-self:flex-end;background:rgba(0,170,255,0.15);border-left:3px solid #00aaff}
.chat-msg.eva{align-self:flex-start;background:rgba(0,255,136,0.08);border-left:3px solid #00ff88}
.chat-msg .time{font-size:9px;color:#446688;margin-bottom:4px}
#chat-input{display:flex;gap:8px;padding:10px;border-top:1px solid rgba(68,102,136,0.1)}
#chat-input input{flex:1;background:rgba(15,20,35,0.6);border:1px solid rgba(0,170,255,0.12);border-radius:10px;padding:10px 14px;color:#e8e8f0;font-size:12px;outline:none;transition:all 0.2s}
#chat-input input:focus{border-color:#00aaff}
#chat-input button{background:linear-gradient(135deg,#0088cc,#00aaff);border:none;border-radius:10px;padding:10px 18px;color:#fff;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.2s;box-shadow:0 2px 12px rgba(0,170,255,0.2)}
#chat-input button:hover{background:#0088cc}

.flow-row{display:flex;align-items:center;gap:5px;padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.03);font-size:10px;font-family:'JetBrains Mono','SF Mono',Menlo,monospace;color:#88aacc}
.flow-row .t{color:#446688;min-width:55px}
.flow-row .s{color:#00ff88;font-weight:600;min-width:65px}
.flow-row .top{color:#aaccff;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.flow-row .st{font-size:8px;padding:1px 4px;border-radius:3px;font-weight:600;text-transform:uppercase}

.node-label{position:absolute;font-size:10px;font-weight:500;text-shadow:0 0 4px #000,0 0 8px #000;background:rgba(5,5,16,0.85);padding:2px 8px;border-radius:6px;pointer-events:none;white-space:nowrap;z-index:5;transform:translate(-50%,-50%);border:1px solid rgba(255,255,255,0.04)}

#info-panel{position:fixed;z-index:500;background:rgba(8,8,20,0.85);padding:16px 20px;border-radius:16px;border:1px solid rgba(255,255,255,0.06);max-width:280px;pointer-events:none;opacity:0;transition:all 0.3s cubic-bezier(0.4,0,0.2,1);transform:translateY(-5px);backdrop-filter:blur(20px);box-shadow:0 8px 40px rgba(0,0,0,0.6)}
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

<div id="info-panel">
  <h3 id="info-name">-</h3>
  <div class="tag" id="info-tag"></div>
  <div class="props" id="info-props"></div>
  <div class="tools" id="info-tools" style="display:none"></div>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
var scene, camera, renderer, controls;
var nodes = {};
var flowParticles = [];
var raycaster, pointer;
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

function loadToolSatellites() {
  // Clear old tool meshes first
  if (window._toolMeshes) {
    for (var k in window._toolMeshes) {
      var t = window._toolMeshes[k];
      if (t.parent) t.parent.remove(t);
      if (t.geometry) t.geometry.dispose();
      if (t.material) t.material.dispose();
      if (t.userData.labelEl) t.userData.labelEl.remove();
    }
  }
  window._toolMeshes = {};
  
  fetch('/api/tools').then(function(r) { return r.json(); }).then(function(td) {
    var toolsData = td.tools || {};
    var toolMeshes = {};
    for (var agentKey in toolsData) {
      var agentNode = null;
      for (var nk in nodes) {
        var nm = nodes[nk].userData.name || '';
        if (nm.toLowerCase().replace(/^adam-/, '') === agentKey.toLowerCase().replace(/^adam-/, '')) {
          agentNode = nodes[nk];
          break;
        }
      }
      if (!agentNode) continue;

      var allTools = (toolsData[agentKey].scripts || []).concat(toolsData[agentKey].tools || []);
      for (var ti = 0; ti < Math.min(allTools.length, 8); ti++) {
        var toolName = allTools[ti];
        var angle = (2 * Math.PI * ti) / Math.max(allTools.length, 1);
        var orbitR = 0.6 + (ti % 3) * 0.15;
        var tGeom = new THREE.OctahedronGeometry(0.06, 0);
        var tMat = new THREE.MeshPhongMaterial({color: 0xffaa00, emissive: 0xff8800, emissiveIntensity: 0.4});
        var tMesh = new THREE.Mesh(tGeom, tMat);
        tMesh.position.copy(agentNode.position);
        tMesh.userData = {name: toolName, label: 'Tool', parent: agentNode, angle: angle, orbitR: orbitR};
        scene.add(tMesh);
        toolMeshes[agentKey + '_' + ti] = tMesh;

        // Tool label (remove old if exists)
        if (tMesh.userData.labelEl) { tMesh.userData.labelEl.remove(); }
        var tl = document.createElement('div');
        tl.className = 'node-label';
        tl.textContent = toolName.substring(0, 15);
        tl.style.color = '#ffaa00';
        tl.style.fontSize = '7px';
        tl.style.fontWeight = '400';
        document.body.appendChild(tl);
        tMesh.userData.labelEl = tl;
      }
    }
    window._toolMeshes = toolMeshes;
  }).catch(function(e) { console.log('Tools load error:', e); });
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

  // NUCLEAR CLEAR — remove everything, rebuild from scratch
  // Save lights and stars
  var saved = [];
  for (var i = scene.children.length - 1; i >= 0; i--) {
    var ch = scene.children[i];
    if (ch.isLight || ch.isPoints) {
      saved.push(ch);
      scene.remove(ch);
    } else {
      scene.remove(ch);
      if (ch.geometry) ch.geometry.dispose();
      if (ch.material) { if (ch.material.length) { ch.material.forEach(function(m){m.dispose();}); } else { ch.material.dispose(); } }
    }
  }
  // Clear scene completely
  while(scene.children.length > 0) {
    var obj = scene.children[0];
    scene.remove(obj);
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) { if (obj.material.length) { obj.material.forEach(function(m){m.dispose();}); } else { obj.material.dispose(); } }
  }
  // Restore lights and stars
  for (var i = 0; i < saved.length; i++) {
    scene.add(saved[i]);
  }
  
  // Clear tool meshes
  window._toolMeshes = {};
  
  // Clear all labels
  document.querySelectorAll('.node-label').forEach(function(el) { el.remove(); });
  
  nodes = {};
  flowParticles = [];

  var edges = data.edges || [];
  var nodePositions = {};

  if (hub.eva) {
    nodePositions['eva'] = new THREE.Vector3(0, 0, 0);
  }

  var svcRadius = 2.5;
  for (var i = 0; i < hub.services.length; i++) {
    var angle = (2 * Math.PI * i) / hub.services.length;
    nodePositions[hub.services[i].id] = new THREE.Vector3(Math.cos(angle) * svcRadius, Math.sin(angle) * svcRadius * 0.3, Math.sin(angle) * svcRadius);
  }

  var agentRadius = 5.5;
  for (var i = 0; i < hub.agents.length; i++) {
    var angle = (2 * Math.PI * i) / hub.agents.length - Math.PI / 2;
    nodePositions[hub.agents[i].id] = new THREE.Vector3(Math.cos(angle) * agentRadius, Math.sin(angle * 2) * 0.8, Math.sin(angle) * agentRadius);
  }

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
      // Single subtle glow - no extra spheres
      var glow = new THREE.Mesh(new THREE.SphereGeometry(size * 1.3, 32, 32), new THREE.MeshBasicMaterial({color: 0x00aaff, transparent: true, opacity: 0.04, side: THREE.BackSide}));
      glow.position.copy(pos);
      scene.add(glow);
    }

    if (mesh.userData.labelEl) { mesh.userData.labelEl.remove(); }
    var l = document.createElement('div');
    l.className = 'node-label';
    l.textContent = n.label === 'SkillDomain' ? n.name.substring(0, 10) : n.name;
    l.style.color = cfg.clr;
    l.style.fontSize = n.label === 'EVA' ? '14px' : (n.label === 'Agent' ? '10px' : (n.label === 'Service' ? '9px' : '7px'));
    l.style.fontWeight = n.label === 'EVA' ? '700' : '500';
    document.body.appendChild(l);
    mesh.userData.labelEl = l;
  }

  var edgeCurves = [];
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
        var opacity = Math.min(0.3, 0.5 - dist * 0.02);
        // Highlight agent→skill edges
        if (e.relation === 'has_skill' && (nodes[e.source].userData.label === 'Agent' || nodes[e.target].userData.label === 'SkillDomain')) {
          opacity = Math.min(0.35, 0.6 - dist * 0.02);
        }
        scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({color: (e.relation === 'orchestrates' || e.relation === 'reports_to') ? 0x00aaff : (e.relation === 'has_skill' ? 0x6688cc : 0x446688), transparent: true, opacity: opacity})));
        edgeCurves.push({source: e.source, target: e.target, curve: curve});
      }
    }
  }

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

  // Flow particles
  function spawnFlows() {
    var agentKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'Agent'; });
    var svcKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'Service'; });
    var allKeys = agentKeys.concat(svcKeys);
    for (var i = 0; i < 8 && allKeys.length > 1; i++) {
      var src = allKeys[Math.floor(Math.random() * allKeys.length)];
      var dst = allKeys[Math.floor(Math.random() * allKeys.length)];
      if (src !== dst && nodes[src] && nodes[dst]) {
        var size = 0.04 + Math.random() * 0.04;
        var color = Math.random() > 0.7 ? 0xff4466 : 0x00ff88;
        var geom = new THREE.SphereGeometry(size, 8, 8);
        var mat = new THREE.MeshBasicMaterial({color: color, transparent: true, opacity: 0.8});
        var mesh = new THREE.Mesh(geom, mat);
        scene.add(mesh);
        var curve = new THREE.QuadraticBezierCurve3(nodes[src].position, new THREE.Vector3().addVectors(nodes[src].position, nodes[dst].position).multiplyScalar(0.5), nodes[dst].position);
        flowParticles.push({
          mesh: mesh,
          curve: curve,
          progress: Math.random(),
          speed: 0.008 + Math.random() * 0.006,
          glow: new THREE.Mesh(new THREE.SphereGeometry(size * 2.5, 8, 8), new THREE.MeshBasicMaterial({color: color, transparent: true, opacity: 0.02}))
        });
        scene.add(flowParticles[flowParticles.length - 1].glow);
      }
    }
  }
  // Load tools as satellites (inline, not separate call)
  fetch('/api/tools').then(function(r) { return r.json(); }).then(function(td) {
    var toolsData = td.tools || {};
    var toolMeshes = {};
    for (var agentKey in toolsData) {
      var agentNode = null;
      for (var nk in nodes) {
        var nm = (nodes[nk].userData.name || '').toLowerCase().replace(/^adam-/, '');
        if (nm === agentKey.toLowerCase().replace(/^adam-/, '')) {
          agentNode = nodes[nk];
          break;
        }
      }
      if (!agentNode) continue;
      var allTools = (toolsData[agentKey].scripts || []).concat(toolsData[agentKey].tools || []);
      for (var ti = 0; ti < Math.min(allTools.length, 6); ti++) {
        var toolName = allTools[ti];
        var angle = (2 * Math.PI * ti) / Math.max(allTools.length, 1);
        var orbitR = 0.6 + (ti % 3) * 0.15;
        var tGeom = new THREE.OctahedronGeometry(0.06, 0);
        var tMat = new THREE.MeshPhongMaterial({color: 0xffaa00, emissive: 0xff8800, emissiveIntensity: 0.4});
        var tMesh = new THREE.Mesh(tGeom, tMat);
        tMesh.position.copy(agentNode.position);
        tMesh.userData = {name: toolName, label: 'Tool', parent: agentNode, angle: angle, orbitR: orbitR};
        scene.add(tMesh);
        toolMeshes[agentKey + '_' + ti] = tMesh;
        var tl = document.createElement('div');
        tl.className = 'node-label';
        tl.textContent = toolName.substring(0, 15);
        tl.style.color = '#ffaa00';
        tl.style.fontSize = '7px';
        tl.style.fontWeight = '400';
        document.body.appendChild(tl);
        tMesh.userData.labelEl = tl;
      }
    }
    window._toolMeshes = toolMeshes;
  }).catch(function(e) {});

  spawnFlows();
  
  // Spawn skill interaction particles (agent → skill)
  var skillFlows = [];
  for (var i = 0; i < 5 && Object.keys(nodes).length > 1; i++) {
    var agentKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'Agent'; });
    var skillKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'SkillDomain'; });
    if (agentKeys.length > 0 && skillKeys.length > 0) {
      var src = agentKeys[Math.floor(Math.random() * agentKeys.length)];
      var dst = skillKeys[Math.floor(Math.random() * skillKeys.length)];
      if (src !== dst && nodes[src] && nodes[dst]) {
        var size = 0.03;
        var geom = new THREE.SphereGeometry(size, 6, 6);
        var mat = new THREE.MeshBasicMaterial({color: 0x6688ff, transparent: true, opacity: 0.6});
        var mesh = new THREE.Mesh(geom, mat);
        scene.add(mesh);
        var curve = new THREE.QuadraticBezierCurve3(nodes[src].position, new THREE.Vector3().addVectors(nodes[src].position, nodes[dst].position).multiplyScalar(0.5), nodes[dst].position);
        flowParticles.push({
          mesh: mesh,
          curve: curve,
          progress: Math.random(),
          speed: 0.005 + Math.random() * 0.003,
          glow: new THREE.Mesh(new THREE.SphereGeometry(size * 2, 6, 6), new THREE.MeshBasicMaterial({color: 0x6688ff, transparent: true, opacity: 0.015}))
        });
        scene.add(flowParticles[flowParticles.length - 1].glow);
      }
    }
  }

  // Show real stats (from /api/stats)
  fetch('/api/stats').then(function(r) { return r.json(); }).then(function(s) {
    document.getElementById('stats-bar').innerHTML = 
      '<div>Agents: <span class="val">' + (s.agents || hub.agents.length) + '</span></div>' +
      '<div>Skills: <span class="val">' + (s.skills || hub.skills.length) + '</span></div>' +
      '<div>Outils: <span class="val">' + (s.tools || 0) + '</span></div>' +
      '<div>Leçons: <span class="val">' + (s.lessons || 0) + '</span></div>';
  }).catch(function() {
    document.getElementById('stats-bar').innerHTML = '<div>Agents: <span class="val">' + hub.agents.length + '</span></div><div>Skills: <span class="val">' + hub.skills.length + '</span></div><div>Services: <span class="val">' + hub.services.length + '</span></div>';
  });
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

  for (var i = flowParticles.length - 1; i >= 0; i--) {
    var p = flowParticles[i];
    p.progress += p.speed;
    if (p.progress > 1) {
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

  // Animate tool satellites orbiting their agents
  var tm = window._toolMeshes || {};
  var now = Date.now() * 0.001;
  for (var tk in tm) {
    var t = tm[tk];
    if (t.userData.parent) {
      var ang = t.userData.angle + now * 0.5;
      var r = t.userData.orbitR;
      t.position.x = t.userData.parent.position.x + Math.cos(ang) * r;
      t.position.z = t.userData.parent.position.z + Math.sin(ang) * r;
      t.position.y = t.userData.parent.position.y + 0.2 + Math.sin(now * 2 + t.userData.angle) * 0.05;
      t.rotation.y += 0.02;

      // Update tool label position
      if (t.userData.labelEl) {
        var pos = t.position.clone();
        pos.project(camera);
        if (pos.z < 1) {
          var w = renderer.domElement.clientWidth;
          var h = renderer.domElement.clientHeight;
          t.userData.labelEl.style.left = ((pos.x * 0.5 + 0.5) * w) + 'px';
          t.userData.labelEl.style.top = ((-pos.y * 0.5 + 0.5) * h) + 'px';
          var dist = camera.position.distanceTo(t.position);
          t.userData.labelEl.style.display = dist < 12 ? 'block' : 'none';
        } else {
          t.userData.labelEl.style.display = 'none';
        }
      }
    }
  }

  // Flash random skill nodes to show "skill calls"
  if (Math.random() < 0.02 && Object.keys(nodes).length > 0) {
    var skillKeys = Object.keys(nodes).filter(function(k) { return nodes[k].userData.label === 'SkillDomain'; });
    if (skillKeys.length > 0) {
      var sk = skillKeys[Math.floor(Math.random() * skillKeys.length)];
      var sm = nodes[sk];
      sm.material.emissiveIntensity = 0.8;
      setTimeout(function() { if (sm.material) sm.material.emissiveIntensity = 0.15; }, 300);
    }
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

// ─── Panel System ───
function togglePanel(id) {
  var p = document.getElementById(id);
  p.classList.toggle('collapsed');
}

function minimizePanel(id) {
  var p = document.getElementById(id);
  p.classList.toggle('minimized');
}

var dragState = {};

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

// ─── Start ───
init();
fetchAgents();
fetchMissions();
fetchPackets();
loadToolSatellites();
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
