#!/usr/bin/env python3
"""Adam-Verifier — Valide les outils créés par les agents

Vérifie que chaque outil est:
1. Du vrai code Python (pas du texte)
2. Fonctionnel (compile sans erreur)
3. A des implémentations réelles (pas que des 'pass')
4. N'est pas vide

Si invalide → demande à Qwen de régénérer le code
"""
import os, sys, ast, json, re
from pathlib import Path
from datetime import datetime

BASE = Path(os.environ.get("ADAM_V2_DIR", "/home/aza/eva-adam-v2"))
VLLM_URL = os.environ.get("VLLM_URL", "http://localhost:8000")

def call_qwen(prompt, max_tokens=1024):
    import urllib.request
    payload = json.dumps({
        "model": "Qwen2.5-32B-Instruct-AWQ",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }).encode()
    try:
        req = urllib.request.Request(f"{VLLM_URL}/v1/chat/completions",
                                     data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Erreur Qwen: {e}")
        return ""

def is_valid_python(code):
    """Check if code is valid Python that compiles"""
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False

def has_real_implementation(code):
    """Check if code has actual implementations (not just pass/TODO)"""
    if not code.strip():
        return False
    # Count pass/TODO statements
    lines = code.split("\n")
    total_lines = len([l for l in lines if l.strip()])
    pass_lines = len([l for l in lines if l.strip() == "pass" or "TODO" in l or "..." in l.strip()])
    if total_lines == 0:
        return False
    # If more than 50% is pass/TODO, it's a skeleton
    if total_lines > 3 and pass_lines / total_lines > 0.5:
        return False
    return True

def validate_and_fix_tool(tool_path):
    """Validate a tool and fix it if needed"""
    name = tool_path.name
    try:
        code = tool_path.read_text()
    except:
        return {"tool": name, "status": "empty", "action": "skip"}
    
    issues = []
    
    # Check if it's text (not Python)
    if not is_valid_python(code):
        issues.append("not_python")
    
    # Check if it has real implementations
    if not has_real_implementation(code):
        issues.append("skeleton")
    
    if not issues:
        return {"tool": name, "status": "valid", "issues": []}
    
    # Need to regenerate
    print(f"  ❌ {name}: {', '.join(issues)} — régénération...")
    
    # Read description from registry if available
    desc = code[:200] if code.strip() else f"Outil {name}"
    
    prompt = f"""Tu dois écrire du CODE PYTHON FONCTIONNEL pour l'outil '{name.replace('.py','')}'.
    
Contexte: {desc}

RÈGLES:
- Le code doit être du VRAI Python qui compile
- PAS de 'pass', 'TODO', ou '...' comme implémentation
- Inclure les imports nécessaires
- Les fonctions doivent avoir de vraies implémentations
- Ajouter un block if __name__ == '__main__' avec un test
- Réponds UNIQUEMENT avec le code Python (pas de markdown, pas d'explication)
"""
    
    new_code = call_qwen(prompt, max_tokens=1024)
    
    # Extract code from markdown if present
    if "```python" in new_code:
        new_code = new_code.split("```python")[1].split("```")[0]
    elif "```" in new_code:
        new_code = new_code.split("```")[1].split("```")[0]
    
    # Validate new code
    if is_valid_python(new_code) and has_real_implementation(new_code):
        tool_path.write_text(new_code)
        print(f"  ✅ {name}: régénéré avec succès ({len(new_code)} chars)")
        return {"tool": name, "status": "fixed", "issues": issues, "new_size": len(new_code)}
    else:
        print(f"  ⚠️ {name}: régénération échouée, code encore invalide")
        return {"tool": name, "status": "failed_fix", "issues": issues}

def scan_all():
    """Scan all agent tools"""
    print("=" * 60)
    print("Adam-Verifier — Validation des outils")
    print("=" * 60)
    
    results = {"valid": 0, "fixed": 0, "failed": 0, "total": 0}
    agents_dir = BASE / "agents"
    
    if not agents_dir.exists():
        print("Dossier agents introuvable")
        return
    
    for agent_dir in sorted(agents_dir.iterdir()):
        if not agent_dir.is_dir():
            continue
        tools_dir = agent_dir / "tools"
        if not tools_dir.exists():
            continue
        
        for tool_file in sorted(tools_dir.glob("*.py")):
            if "registry" in tool_file.name or "self_improvement" in tool_file.name or "runtime_backup" in tool_file.name:
                continue
            if "backups" in str(tool_file):
                continue
            
            results["total"] += 1
            print(f"\n🔍 {agent_dir.name}/{tool_file.name}")
            r = validate_and_fix_tool(tool_file)
            
            if r["status"] == "valid":
                results["valid"] += 1
                print(f"  ✅ Valide")
            elif r["status"] == "fixed":
                results["fixed"] += 1
            elif r["status"] == "failed_fix":
                results["failed"] += 1
    
    print(f"\n{'=' * 60}")
    print(f"RÉSULTAT: {results['valid']} valides, {results['fixed']} réparés, {results['failed']} échoués sur {results['total']} outils")
    
    # Publish to Go Bus
    try:
        import urllib.request
        payload = json.dumps({
            "topic": "adam:verifier:done",
            "source": "adam-verifier",
            "payload": results,
            "priority": 1
        }).encode()
        req = urllib.request.Request("http://localhost:8086/api/publish",
                                     data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=3)
    except:
        pass
    
    return results

if __name__ == "__main__":
    scan_all()
