import nmap
from typing import List, Tuple

def scan_network(ip_range: str) -> List[Tuple[str, str]]:
    nm = nmap.PortScanner()
    nm.scan(hosts=ip_range, arguments='-sn')
    active_hosts = [(host, nm[host]['status']['state']) for host in nm.all_hosts()]
    return active_hosts