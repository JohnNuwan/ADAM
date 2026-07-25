#!/usr/bin/env python3
"""
ADAM Memory System — Mémoire long-terme par agent.

Chaque Adam garde:
- Historique des missions accomplies
- Leçons apprises (what worked, what failed)
- Préférences et patterns
- Indexées par mission type pour retrieval rapide
"""
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


class AdamMemory:
    """Mémoire persistante d'un agent Adam."""

    def __init__(self, agent_name: str):
        base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
        self.agent_name = agent_name
        self.memory_dir = base / "agents" / agent_name.replace("adam-", "") / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.missions_file = self.memory_dir / "missions.json"
        self.lessons_file = self.memory_dir / "lessons.json"
        self._load()

    def _load(self):
        """Charge la mémoire depuis le disque."""
        self.missions = self._load_json(self.missions_file, {"missions": []})
        self.lessons = self._load_json(self.lessons_file, {"lessons": []})

    def _load_json(self, path: Path, default: dict) -> dict:
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return default

    def _save_json(self, path: Path, data: dict):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_mission(self, mission: str, result: dict, steps: list = None):
        """Sauvegarde une mission accomplie."""
        entry = {
            "id": f"m_{len(self.missions['missions']) + 1}",
            "mission": mission,
            "result": result,
            "steps": steps or [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": self.agent_name,
        }
        self.missions["missions"].append(entry)
        self._save_json(self.missions_file, self.missions)
        return entry["id"]

    def get_recent_missions(self, limit: int = 10) -> list:
        """Retourne les missions les plus récentes."""
        return self.missions["missions"][-limit:]

    def save_lesson(self, lesson: str, context: str = "", mission_type: str = ""):
        """Sauvegarde une leçon apprise."""
        entry = {
            "lesson": lesson,
            "context": context,
            "mission_type": mission_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.lessons["lessons"].append(entry)
        self._save_json(self.lessons_file, self.lessons)

    def get_relevant_lessons(self, mission: str, limit: int = 5) -> list:
        """Retourne les leçons pertinentes pour une mission (recherche simple par mots-clés)."""
        mission_words = set(mission.lower().split())
        scored = []
        for lesson in self.lessons["lessons"]:
            lesson_words = set(lesson.get("context", "").lower().split() +
                             lesson.get("lesson", "").lower().split() +
                             lesson.get("mission_type", "").lower().split())
            overlap = len(mission_words & lesson_words)
            scored.append((overlap, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:limit] if s[0] > 0]

    def get_summary(self) -> dict:
        """Retourne un résumé de la mémoire."""
        total = len(self.missions["missions"])
        success = sum(1 for m in self.missions["missions"] if m.get("result", {}).get("success"))
        return {
            "agent": self.agent_name,
            "total_missions": total,
            "successful": success,
            "success_rate": (success / total * 100) if total > 0 else 0,
            "total_lessons": len(self.lessons["lessons"]),
            "memory_dir": str(self.memory_dir),
        }

    def get_context_for_llm(self, mission: str) -> str:
        """Génère un contexte formaté pour le LLM."""
        recent = self.get_recent_missions(3)
        lessons = self.get_relevant_lessons(mission, 3)

        ctx = f"## Mémoire de {self.agent_name}\n\n"
        ctx += f"Missions accomplies: {len(recent)} récentes / {len(self.missions['missions'])} total\n\n"

        if recent:
            ctx += "### Missions récentes:\n"
            for m in recent:
                success = "✅" if m.get("result", {}).get("success") else "❌"
                ctx += f"- {success} {m['mission'][:80]}\n"

        if lessons:
            ctx += "\n### Leçons apprises:\n"
            for l in lessons:
                ctx += f"- {l['lesson']}\n"

        return ctx
