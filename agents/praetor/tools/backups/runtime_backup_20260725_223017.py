#!/usr/bin/env python3
"""
ADAM Runtime V5 — Moteur d'agent autonome.

Chaque Adam est un agent IA qui:
1. Reçoit une mission (depuis Go Bus ou directement)
2. Réfléchit avec le LLM (vLLM Qwen2.5-32B local)
3. Planifie les étapes
4. Exécute (outils existants ou nouveaux)
5. Crée des outils si besoin
6. Sauvegarde l'apprentissage (mémoire + skills)
7. Peut déléguer à d'autres Adams
8. Reporte le résultat sur Go Bus
"""
import os
import logging
logger = logging.getLogger(__name__)
import sys
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))
from adam_tools import ToolSystem
from adam_memory import AdamMemory


class AdamRuntime:
    """Runtime d'un agent Adam autonome."""

    def __init__(self, agent_name: str, role: str = "", vllm_url: str = None):
        self.agent_name = agent_name
        self.role = role
        self.vllm_url = vllm_url or os.environ.get("VLLM_URL", "http://localhost:8000")
        self.model = os.environ.get("VLLM_MODEL", "Qwen2.5-32B-Instruct-AWQ")
        self.bus_url = os.environ.get("GO_BUS_URL", "http://localhost:8086/api/publish")

        # Sub-systems
        self.tools = ToolSystem(agent_name)
        self.memory = AdamMemory(agent_name)

        # Workspace
        base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
        self.workspace = base / "agents" / agent_name.replace("adam-", "")

    def _llm(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """Appelle le LLM local (vLLM) pour réfléchir."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }).encode()

        try:
            req = urllib.request.Request(
                f"{self.vllm_url}/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM ERROR] {e}"

    def _bus_publish(self, topic: str, payload: dict):
        """Publie un événement sur le Go Bus."""
        data = json.dumps({
            "topic": topic,
            "source": self.agent_name,
            "payload": payload,
            "priority": 1,
        }).encode()
        try:
            req = urllib.request.Request(self.bus_url, data=data,
                                        headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def run_mission(self, mission: str) -> dict:
        """Exécute une mission complète: réfléchir → planifier → agir → apprendre."""
        start_time = time.time()
        self._bus_publish("adam:mission:started", {
            "agent": self.agent_name, "mission": mission,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # 1. Contexte: mémoire + outils disponibles
        memory_ctx = self.memory.get_context_for_llm(mission)
        tools_list = self.tools.list_tools()
        tools_str = "\n".join(f"- {t['name']} ({t['type']}): {t['description']}" for t in tools_list) or "Aucun outil"

        # 2. Réfléchir et planifier
        system_prompt = f"""Tu es {self.agent_name}, un agent IA autonome du système ADAM.
Rôle: {self.role}
Tu reçois des missions, tu les Accomplis en utilisant tes outils ou en créant de nouveaux outils.
Tu réponds en JSON avec le format suivant:
{{"plan": [{{"action": "execute_tool|create_tool|delegate|create_agent|self_modify|manage_infra|research|report", "tool": "nom_outil", "args": "...", "code": "...", "target_agent": "...", "description": "..."}}]}}

Outils disponibles:
{tools_str}

{memory_ctx}"""

        think_prompt = f"Mission: {mission}\n\nÉlabore un plan d'action en JSON:"
        # Lire la mémoire pour apprendre du passé
        lessons_str = ""
        try:
            lessons = self.memory.get_relevant_lessons(mission, limit=3)
            if lessons:
                lessons_str = "\n\nLeçons apprises:\n"
                for i, l in enumerate(lessons[:3]):
                    lessons_str += f"{i+1}. {l.get('lesson', '')}\n"
        except:
            pass

        recent_str = ""
        try:
            recent = self.memory.get_recent_missions(limit=3)
            if recent:
                recent_str = "\nMissions récentes:\n"
                for m in recent[:3]:
                    s = m.get('result', {}).get('success', False)
                    recent_str += f"- {m.get('mission', '')[:50]} -> {'OK' if s else 'KO'}\n"
        except:
            pass

        # Injecter la mémoire dans le prompt
        think_prompt = think_prompt + lessons_str + recent_str + "\nIMPORTANT: Utilise les leçons pour éviter les erreurs. Réutilise les outils existants."

        plan_response = self._llm(think_prompt, system=system_prompt, max_tokens=2048)

        # 3. Parser le plan
        plan = self._parse_plan(plan_response)
        
        # 3b. Forcer l'évolution AGI — injecter self_modify ou manage_infra
        # si l'agent n'a pas d'action AGI dans son plan
        has_agi = any(s.get("action") in ("create_agent", "self_modify", "manage_infra") for s in plan)
        if not has_agi and len(plan) > 0:
            # Alternate between self_modify and manage_infra
            import random as _rnd
            agi_choice = _rnd.choice(["self_modify", "manage_infra"])
            
            if agi_choice == "self_modify":
                # Inject self_modify — simple, no LLM dependency for the injection
                improvements = [
                    ("Ajouter un cache aux outils pour éviter les appels dupliqués", "CACHE = {}\ndef cached_call(key, func, *args):\n    if key not in CACHE:\n        CACHE[key] = func(*args)\n    return CACHE[key]"),
                    ("Ajouter un système de retry aux outils", "import time\ndef retry(func, max=3):\n    for i in range(max):\n        try: return func()\n        except: time.sleep(1)\n    return None"),
                    ("Ajouter un logging des appels d'outils", "import logging\nlog = logging.getLogger(__name__)\ndef log_call(name, result):\n    log.info(f'Tool {name}: {result}')"),
                    ("Optimiser la gestion d'erreur des outils", "def safe_exec(func):\n    try: return func()\n    except Exception as e: return {'error': str(e)}"),
                ]
                import random as _r2
                what, code = _r2.choice(improvements)
                plan.append({
                    "action": "self_modify",
                    "what": what,
                    "code": code
                })
                logger.info(f"AGI-4: self_modify injecté: {what[:50]}")
            
            elif agi_choice == "manage_infra":
                # Inject manage_infra to check container health
                plan.append({
                    "action": "manage_infra",
                    "infra_action": "status",
                    "description": "Vérifier la santé des conteneurs Docker"
                })
                logger.info("AGI-5: manage_infra injecté (health check)")

        # 4. Exécuter le plan
        results = []
        for step in plan:
            result = self._execute_step(step, mission)
            results.append({"step": step, "result": result})

        # 5. Évaluer le résultat
        success = all(r["result"].get("success", False) for r in results) if results else False
        elapsed = round(time.time() - start_time, 2)

        final_result = {
            "agent": self.agent_name,
            "mission": mission,
            "success": success,
            "steps": len(results),
            "elapsed_s": elapsed,
            "results": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 6. Sauvegarder en mémoire
        self.memory.save_mission(mission, final_result, [r["step"] for r in results])

        # 7. Apprendre une leçon
        if results:
            lesson_prompt = f"Mission: {mission}\nRésultat: {'succès' if success else 'échec'}\nQuelle leçon retenir? Réponds en une phrase:"
            lesson = self._llm(lesson_prompt, max_tokens=256)
            self.memory.save_lesson(lesson.strip(), mission_type=mission.split()[0] if mission else "")

        # 8. Publier le résultat
        self._bus_publish("adam:mission:done", final_result)

        return final_result

    def _parse_plan(self, response: str) -> list:
        """Parse la réponse du LLM en plan d'action."""
        # Essayer de parser le JSON
        try:
            # Trouver le JSON dans la réponse
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                return data.get("plan", [])
        except json.JSONDecodeError:
            pass

        # Fallback: traiter la réponse comme une action simple
        return [{"action": "report", "description": response[:500]}]

    def _execute_step(self, step: dict, mission: str) -> dict:
        """Exécute une étape du plan."""
        action = step.get("action", "report")

        if action == "execute_tool":
            tool_name = step.get("tool", "")
            args = step.get("args", "")
            # Chercher l'outil par nom
            for tid, info in self.tools.registry["tools"].items():
                if info["name"] == tool_name:
                    return self.tools.execute_tool(tid, args)
            return {"error": f"Outil '{tool_name}' introuvable"}

        elif action == "create_tool":
            name = step.get("tool", f"tool_{int(time.time())}")
            code = step.get("code", "")
            tool_type = step.get("type", "python")
            desc = step.get("description", "")
            if code:
                return self.tools.create_tool(name, code, tool_type, desc)
            return {"error": "Pas de code fourni"}

        elif action == "delegate":
            target = step.get("target_agent", "")
            subtask = step.get("description", "")
            self._bus_publish("adam:mission", {
                "agent": target, "mission": subtask,
                "delegated_by": self.agent_name,
            })
            return {"status": "delegated", "target": target, "subtask": subtask}

        elif action == "create_agent":
            # AGI Niveau 3: Créer un nouvel agent spécialisé
            agent_name = step.get("agent_name", "adam-new")
            role = step.get("role", step.get("description", ""))
            first_mission = step.get("mission", step.get("description", ""))
            import os as _os
            from pathlib import Path as _Path
            import json as _json
            dir_name = agent_name.replace("adam-", "")
            agent_dir = _Path(f"/home/aza/eva-adam-v2/agents/{dir_name}")
            agent_dir.mkdir(parents=True, exist_ok=True)
            (agent_dir / "tools").mkdir(exist_ok=True)
            (agent_dir / "memory").mkdir(exist_ok=True)
            (agent_dir / "memory" / "missions.json").write_text(_json.dumps({"missions": []}))
            (agent_dir / "memory" / "lessons.json").write_text(_json.dumps({"lessons": []}))
            self._bus_publish("adam:agent:created", {"new_agent": agent_name, "role": role, "created_by": self.agent_name})
            self._bus_publish("adam:mission", {"agent": agent_name, "mission": first_mission, "status": "pending"})
            logger.info(f"AGI-3: Nouvel agent créé: {agent_name} ({role})")
            print(f"AGI-3: Nouvel agent créé: {agent_name} ({role})")
            return {"agent_name": agent_name, "role": role, "status": "created", "created_by": self.agent_name}

        elif action == "self_modify":
            # AGI Niveau 4: Auto-modification (sécurisée)
            what = step.get("what", step.get("description", ""))
            new_code = step.get("code", "")
            import shutil as _shutil
            from datetime import datetime as _dt
            import os as _os
            from pathlib import Path as _Path
            ts = _dt.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = _Path(f"/home/aza/eva-adam-v2/agents/{self.agent_name.replace('adam-','')}/tools/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_file = backup_dir / f"runtime_backup_{ts}.py"
            _shutil.copy2(_Path(__file__), backup_file)
            improvement_file = backup_dir.parent / f"self_improvement_{ts}.py"
            improvement_file.write_text(f"# Auto-amélioration de {self.agent_name}\n# Demande: {what}\n# Date: {_dt.now().isoformat()}\n{new_code}\n")
            _os.chmod(improvement_file, 0o755)
            self._bus_publish("adam:self:modified", {"what": what, "file": str(improvement_file), "backup": str(backup_file), "agent": self.agent_name})
            self.memory.save_lesson(f"Auto-amélioration appliquée: {what}", mission_type="self_modify")
            logger.info(f"AGI-4: Self-modify: {what} -> {improvement_file.name}")
            print(f"AGI-4: Auto-amélioration: {what}")
            return {"what": what, "improvement_file": str(improvement_file), "backup": str(backup_file), "status": "improved"}

        elif action == "research":
            # Recherche et analyse via LLM
            query = step.get("query", step.get("description", ""))
            logger.info(f"Recherche: {query[:50]}")
            result = self._llm(f"Analyse détaillée: {query}", max_tokens=512)
            return {"query": query, "result": result[:300], "success": True}

        elif action == "manage_infra":
            # Niveau 5: Auto-gestion infrastructure
            infra_action = step.get("infra_action", step.get("description", ""))
            import subprocess as _sp
            result = {"action": infra_action, "results": []}
            try:
                if "restart" in infra_action.lower() and "container" in infra_action.lower():
                    # Restart a Docker container
                    container = step.get("container", "")
                    if container:
                        r = _sp.run(["docker", "restart", container], capture_output=True, text=True, timeout=30)
                        result["results"].append({"container": container, "exit": r.returncode, "output": r.stdout[:100]})
                        logger.info(f"AGI-5: Restart container {container}")

                elif "scale" in infra_action.lower():
                    # Scale resources (placeholder)
                    result["results"].append({"scaling": "not implemented yet"})

                elif "status" in infra_action.lower() or "health" in infra_action.lower():
                    # Check container health
                    r = _sp.run(["docker", "ps", "--format", "{{.Names}} {{.Status}}"], capture_output=True, text=True, timeout=10)
                    result["results"].append({"containers": r.stdout[:300]})
                    logger.info("AGI-5: Health check")

                elif "clean" in infra_action.lower():
                    # Clean unused resources
                    r = _sp.run(["docker", "system", "prune", "-f"], capture_output=True, text=True, timeout=30)
                    result["results"].append({"pruned": r.stdout[:200]})
                    logger.info("AGI-5: System cleanup")

                elif "deploy" in infra_action.lower():
                    # Deploy/redeploy a service
                    service = step.get("service", "")
                    if service:
                        r = _sp.run(["docker", "compose", "-f", "/home/aza/eva-adam-v2/docker/docker-compose.yml", "up", "-d", service],
                                   capture_output=True, text=True, timeout=60)
                        result["results"].append({"service": service, "exit": r.returncode, "output": r.stdout[:200]})
                        logger.info(f"AGI-5: Deploy {service}")

                else:
                    # Generic infra command
                    cmd = step.get("command", "")
                    if cmd and not any(x in cmd for x in ["rm -rf", "shutdown", "reboot", "mkfs"]):
                        r = _sp.run(cmd.split(), capture_output=True, text=True, timeout=30)
                        result["results"].append({"exit": r.returncode, "output": r.stdout[:200]})

                result["success"] = True
                self._bus_publish("adam:infra:managed", {"action": infra_action, "agent": self.agent_name})
            except Exception as e:
                result["error"] = str(e)
                result["success"] = False
                logger.error(f"AGI-5 infra error: {e}")
            return result

        elif action == "report":
            return {"success": True, "report": step.get("description", "")}

        return {"error": f"Action inconnue: {action}"}

    def status(self) -> dict:
        """Retourne le statut de l'agent."""
        return {
            "agent": self.agent_name,
            "role": self.role,
            "tools": len(self.tools.list_tools()),
            "memory": self.memory.get_summary(),
            "workspace": str(self.workspace),
            "vllm": self.vllm_url,
            "model": self.model,
        }


# ============================================================
# AGENT REGISTRY — Les 14 Adams + EVA
# ============================================================
AGENTS = {
    "eva":          {"role": "Cerveau central - Orchestrateur", "type": "orchestrator"},
    "adam-praetor": {"role": "Auto-correction et maintenance serveurs", "type": "watcher"},
    "adam-sentinel":{"role": "Veille 24/7 - scrapping, monitoring, alerte", "type": "watcher"},
    "adam-critic":  {"role": "Revue de code, qualité, notation SKILL.md", "type": "analysis"},
    "adam-scribe":  {"role": "Rédaction documentation, commits, synthèses", "type": "creation"},
    "adam-skillsmith": {"role": "Création et validation de SKILL.md", "type": "creation"},
    "adam-doctor":  {"role": "Diagnostic et guérison des processus", "type": "watcher"},
    "adam-treasurer": {"role": "Suivi financier, tracking dépenses", "type": "analysis"},
    "adam-social":  {"role": "Gestion réseaux sociaux (Maeve.tech)", "type": "creation"},
    "adam-osint":   {"role": "Collecte OSINT, email, reconnaissance", "type": "collection"},
    "adam-researcher": {"role": "Scan vulnérabilités, recherche académique", "type": "analysis"},
    "adam-rag":     {"role": "Recherche RAG, base de connaissances", "type": "analysis"},
    "adam-viz":     {"role": "Dashboard temps réel + monde 3D", "type": "visualization"},
    "adam-ctf":     {"role": "Challenge CTF autonome", "type": "security"},
    "adam-blue":    {"role": "Hardening et défense", "type": "security"},
    "adam-blue-team": {"role": "Hardening et défense", "type": "security"},
    "adam-red":     {"role": "Tests d'intrusion, OSINT", "type": "security"},
    "adam-red-team":  {"role": "Tests d'intrusion, OSINT", "type": "security"},
}


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ADAM Runtime V5")
    parser.add_argument("agent", help="Nom de l'agent (ex: adam-blue)")
    parser.add_argument("--mission", "-m", help="Mission à accomplir")
    parser.add_argument("--status", "-s", action="store_true", help="Afficher le statut")
    parser.add_argument("--tools", "-t", action="store_true", help="Lister les outils")
    args = parser.parse_args()

    agent_info = AGENTS.get(args.agent)
    if not agent_info:
        print(f"Agent inconnu: {args.agent}")
        print(f"Disponibles: {', '.join(AGENTS.keys())}")
        sys.exit(1)

    runtime = AdamRuntime(args.agent, role=agent_info["role"])

    if args.status:
        print(json.dumps(runtime.status(), indent=2, ensure_ascii=False))
    elif args.tools:
        tools = runtime.tools.list_tools()
        if tools:
            for t in tools:
                print(f"  {t['name']:20s} ({t['type']:6s}) uses={t['uses']} rating={t['rating']}/5  {t['description']}")
        else:
            print("Aucun outil. L'agent peut en créer avec --mission")
    elif args.mission:
        print(f"🐝 {args.agent} reçoit la mission: {args.mission}")
        result = runtime.run_mission(args.mission)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Usage: {sys.argv[0]} <agent> --mission '...' | --status | --tools")
