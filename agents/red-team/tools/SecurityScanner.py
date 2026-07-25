import os
import socket

class SecurityScanner:
    def __init__(self):
        self.open_ports = []

    def scan_port(self, target_ip, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            result = sock.connect_ex((target_ip, port))
            if result == 0:
                self.open_ports.append(port)
            sock.close()
        except Exception as e:
            print(f'Error scanning port {port}: {str(e)}')

    def scan_range(self, target_ip, start_port, end_port):
        for port in range(start_port, end_port + 1):
            self.scan_port(target_ip, port)
        return self.open_ports