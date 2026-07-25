import nmap
from nmap import PortScanner

def scan_network(ip_range):
    nm = PortScanner()
    nm.scan(hosts=ip_range, arguments='-sn')
    hosts_list = [(x, nm[x]['status']['state']) for x in nm.all_hosts()]
    return hosts_list
