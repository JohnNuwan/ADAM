import socket

# Fonction pour scanner les ports
def scan_ports(host):
    open_ports = []
    for port in range(1, 1025):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        result = sock.connect_ex((host, port))
        if result == 0:
            open_ports.append(port)
        sock.close()
    return open_ports

# Exécuter le scan sur le serveur local
local_host = '127.0.0.1'
open_ports = scan_ports(local_host)
print(f'Ports ouverts sur {local_host}: {open_ports}')