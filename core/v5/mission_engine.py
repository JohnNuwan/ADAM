#!/usr/bin/env python3
"""
EVA Mission Engine — L'orchestrateur qui assigne des missions aux Adams.

EVA:
- Reçoit des objectifs (depuis Go Bus, CLI, ou auto)
- Décompose en missions pour les Adams
- Assigne aux meilleurs agents
- Suit l'avancement
- Peut créer des équipes dynamiques
- Évalue les résultats
"""
import os
import sys
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from adam_runtime import AdamRuntime, AGENTS


class MissionEngine:
    """Moteur de missions EVA — l'orchestrateur."""

    def __init__(self, vllm_url: str = None):
        self.vllm_url = vllm_url or os.environ.get("VLLM_URL", "http://localhost:8000")
        self.model = os.environ.get("VLLM_MODEL", "Qwen2.5-32B-Instruct-AWQ")
        self.bus_url = os.environ.get("GO_BUS_URL", "http://localhost:8086/api/publish")

        # File de missions
        base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
        self.queue_file = base / "data" / "mission_queue.json"
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_queue()

        # Équipes dynamiques
        self.teams = {}

    def _load_queue(self):
        if self.queue_file.exists():
            with open(self.queue_file) as f:
                self.queue = json.load(f)
        else:
            self.queue = {"pending": [], "active": [], "done": []}

    def _save_queue(self):
        with open(self.queue_file, "w") as f:
            json.dump(self.queue, f, indent=2, ensure_ascii=False)

    def _llm(self, prompt: str, system: str = "", max_tokens: int = 2048) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = json.dumps({"model": self.model, "messages": messages,
                              "max_tokens": max_tokens, "temperature": 0.7}).encode()
        try:
            req = urllib.request.Request(f"{self.vllm_url}/v1/chat/completions",
                                         data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[LLM ERROR] {e}"

    def _bus_publish(self, topic: str, payload: dict):
        data = json.dumps({"topic": topic, "source": "eva", "payload": payload, "priority": 1}).encode()
        try:
            req = urllib.request.Request(self.bus_url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    def submit_objective(self, objective: str, priority: int = 2) -> str:
        """Soumet un objectif haut-niveau. EVA le décompose en missions."""
        # LLM décompose l'objectif
        agents_desc = "\n".join(f"- {name}: {info['role']}" for name, info in AGENTS.items() if name != "eva")
        system = f"""Tu es EVA, l'orchestrateur du système ADAM. Tu reçois des objectifs et tu les décomposes en missions pour tes agents.

Agents disponibles:
{agents_desc}

Réponds en JSON: {{"missions": [{{"agent": "adam-xxx", "mission": "description claire", "priority": 1-3}}]}}"""

        response = self._llm(f"Objectif: {objective}", system=system)
        missions = self._parse_missions(response)

        # Ajouter à la file
        for m in missions:
            m["objective"] = objective
            m["status"] = "pending"
            m["submitted_at"] = datetime.now(timezone.utc).isoformat()
            self.queue["pending"].append(m)

        self._save_queue()
        self._bus_publish("eva:objective:submitted", {"objective": objective, "missions": len(missions)})
        return f"Objectif '{objective}' → {len(missions)} missions créées"

    def _parse_missions(self, response: str) -> list:
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                return data.get("missions", [])
        except json.JSONDecodeError:
            pass
        return [{"agent": "adam-praetor", "mission": response[:200], "priority": 2}]

    def run_next_mission(self) -> dict:
        """Prend la prochaine mission dans la file et l'exécute."""
        if not self.queue["pending"]:
            return {"status": "empty", "message": "Aucune mission en attente"}

        mission = self.queue["pending"].pop(0)
        agent_name = mission["agent"]
        task = mission["mission"]

        # Vérifier que l'agent existe
        if agent_name not in AGENTS:
            mission["status"] = "failed"
            mission["error"] = f"Agent inconnu: {agent_name}"
            self.queue["done"].append(mission)
            self._save_queue()
            return {"status": "failed", "error": mission["error"]}

        # Lancer l'agent
        mission["status"] = "active"
        mission["started_at"] = datetime.now(timezone.utc).isoformat()
        self.queue["active"].append(mission)
        self._save_queue()

        runtime = AdamRuntime(agent_name, role=AGENTS[agent_name]["role"],
                              vllm_url=self.vllm_url)
        result = runtime.run_mission(task)

        # Déplacer vers done
        self.queue["active"].remove(mission)
        mission["status"] = "done" if result.get("success") else "failed"
        mission["result"] = result
        mission["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.queue["done"].append(mission)
        self._save_queue()

        self._bus_publish("eva:mission:complete", {
            "agent": agent_name, "mission": task, "success": result.get("success"),
        })

        return result

    def run_all_pending(self):
        """Exécute toutes les missions en attente (séquentiel)."""
        while self.queue["pending"]:
            print(f"Missions restantes: {len(self.queue['pending'])}")
            result = self.run_next_mission()
            print(json.dumps(result, indent=2, ensure_ascii=False)[:500])
            time.sleep(1)

    def create_team(self, team_name: str, agent_names: list, objective: str):
        """Crée une équipe dynamique d'agents."""
        team = {
            "name": team_name,
            "agents": agent_names,
            "objective": objective,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.teams[team_name] = team
        self._bus_publish("eva:team:created", team)
        print(f"Équipe '{team_name}' créée: {', '.join(agent_names)}")
        return team

    def get_status(self) -> dict:
        """Retourne l'état de la file de missions."""
        return {
            "pending": len(self.queue["pending"]),
            "active": len(self.queue["active"]),
            "done": len(self.queue["done"]),
            "teams": len(self.teams),
            "agents": len(AGENTS),
        }


# ============================================================
# CLI
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="EVA Mission Engine")
    parser.add_argument("--objective", "-o", help="Soumettre un objectif")
    parser.add_argument("--run", "-r", action="store_true", help="Exécuter la prochaine mission")
    parser.add_argument("--run-all", "-a", action="store_true", help="Exécuter toutes les missions")
    parser.add_argument("--status", "-s", action="store_true", help="Statut de la file")
    parser.add_argument("--team", "-t", nargs="+", help="Créer une équipe (nom agent1 agent2...)")
    args = parser.parse_args()

    engine = MissionEngine()

    if args.objective:
        print(engine.submit_objective(args.objective))
    elif args.run:
        result = engine.run_next_mission()
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])
    elif args.run_all:
        engine.run_all_pending()
    elif args.status:
        print(json.dumps(engine.get_status(), indent=2))
    elif args.team:
        name = args.team[0]
        agents = args.team[1:]
        engine.create_team(name, agents, "Objectif à définir")
    else:
        parser.print_help()
