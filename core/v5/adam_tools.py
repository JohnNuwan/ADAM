#!/usr/bin/env python3
"""
ADAM Tools System — Système d'outils dynamiques pour agents autonomes.

Chaque Adam peut:
- Lister ses outils disponibles
- Créer un nouvel outil (script Python/shell)
- Exécuter un outil
- Partager un outil avec d'autres Adams
- Noter la qualité d'un outil
"""
import os
import json
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


class ToolSystem:
    """Gère les outils d'un Adam."""

    def __init__(self, agent_name: str, tools_dir: str = None):
        self.agent_name = agent_name
        base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
        self.tools_dir = Path(tools_dir or (base / "agents" / agent_name.replace("adam-", "") / "tools"))
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.tools_dir / "registry.json"
        self._load_registry()

    def _load_registry(self):
        """Charge le registre des outils."""
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                self.registry = json.load(f)
        else:
            self.registry = {"tools": {}}

    def _save_registry(self):
        """Sauvegarde le registre."""
        with open(self.registry_file, "w") as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)

    def list_tools(self) -> list:
        """Liste tous les outils disponibles pour cet agent."""
        tools = []
        for tid, info in self.registry["tools"].items():
            tools.append({
                "id": tid,
                "name": info["name"],
                "type": info["type"],
                "description": info.get("description", ""),
                "created_at": info.get("created_at", ""),
                "uses": info.get("uses", 0),
                "rating": info.get("rating", 0),
                "shared": info.get("shared", False),
            })
        return tools

    def create_tool(self, name: str, code: str, tool_type: str = "python",
                    description: str = "", shared: bool = False) -> dict:
        """Crée un nouvel outil et l'enregistre."""
        # ID unique basé sur le nom + hash
        tid = hashlib.md5(f"{self.agent_name}:{name}".encode()).hexdigest()[:12]
        ext = ".py" if tool_type == "python" else ".sh"
        filename = f"{name}{ext}"
        filepath = self.tools_dir / filename

        # Écrire le code
        with open(filepath, "w") as f:
            f.write(code)
        if tool_type == "shell":
            os.chmod(filepath, 0o755)

        # Enregistrer
        self.registry["tools"][tid] = {
            "id": tid,
            "name": name,
            "type": tool_type,
            "description": description,
            "file": filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "uses": 0,
            "rating": 0,
            "shared": shared,
            "created_by": self.agent_name,
        }
        self._save_registry()
        return {"id": tid, "name": name, "file": filename, "status": "created"}

    def execute_tool(self, tool_id: str, args: str = "") -> dict:
        """Exécute un outil par son ID."""
        if tool_id not in self.registry["tools"]:
            return {"error": f"Outil {tool_id} introuvable"}

        tool = self.registry["tools"][tool_id]
        filepath = self.tools_dir / tool["file"]

        if not filepath.exists():
            return {"error": f"Fichier {filepath} introuvable"}

        # Incrémenter le compteur d'usage
        tool["uses"] = tool.get("uses", 0) + 1
        self._save_registry()

        try:
            if tool["type"] == "python":
                cmd = ["python3", str(filepath)]
            else:
                cmd = [str(filepath)]
            if args:
                cmd.extend(args.split())

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return {
                "tool": tool["name"],
                "exit_code": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:500],
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"tool": tool["name"], "error": "timeout (60s)"}
        except Exception as e:
            return {"tool": tool["name"], "error": str(e)}

    def share_tool(self, tool_id: str, target_agent: str) -> dict:
        """Partage un outil avec un autre agent."""
        if tool_id not in self.registry["tools"]:
            return {"error": "Outil introuvable"}

        tool = self.registry["tools"][tool_id]
        filepath = self.tools_dir / tool["file"]

        base = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
        target_dir = base / "agents" / target_agent.replace("adam-", "") / "tools"
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / tool["file"]
        with open(filepath) as src, open(target_file, "w") as dst:
            dst.write(src.read())
        if tool["type"] == "shell":
            os.chmod(target_file, 0o755)

        # Enregistrer dans le registre cible
        target_registry_file = target_dir / "registry.json"
        if target_registry_file.exists():
            with open(target_registry_file) as f:
                target_reg = json.load(f)
        else:
            target_reg = {"tools": {}}

        target_reg["tools"][tool_id] = {**tool, "shared": True, "shared_by": self.agent_name}
        with open(target_registry_file, "w") as f:
            json.dump(target_reg, f, indent=2, ensure_ascii=False)

        tool["shared"] = True
        self._save_registry()
        return {"status": "shared", "tool": tool["name"], "target": target_agent}

    def rate_tool(self, tool_id: str, rating: int) -> dict:
        """Note un outil (1-5)."""
        if tool_id not in self.registry["tools"]:
            return {"error": "Outil introuvable"}
        if not 1 <= rating <= 5:
            return {"error": "Note doit être entre 1 et 5"}

        self.registry["tools"][tool_id]["rating"] = rating
        self._save_registry()
        return {"tool": self.registry["tools"][tool_id]["name"], "rating": rating}
