import nmap
from nmap import PortScannerError

def network_recognition(ip_range):
    try:
        nm = nmap.PortScanner()
        nm.scan(hosts=ip_range, arguments='-sn')
        hosts_list = [(host, nm[host]['status']['state']) for host in nm.all_hosts()]
        return hosts_list
    except PortScannerError as e:
        print(f'An error occurred: {e}')
        return None