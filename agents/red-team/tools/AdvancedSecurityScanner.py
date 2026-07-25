from SecurityScanner import BaseScanner

class AdvancedSecurityScanner(BaseScanner):
    def __init__(self, target_ip, port_range):
        super().__init__(target_ip, port_range)
        self.vulnerability_checks = []

    def add_vulnerability_check(self, check_function):
        self.vulnerability_checks.append(check_function)

    def run_scans(self):
        open_ports = super().run_scans()
        for port in open_ports:
            for check in self.vulnerability_checks:
                print(f'Running vulnerability check {check.__name__} on port {port}')
                result = check(port)
                if result:
                    print(f'Vulnerability found on port {port}: {result}')

# Example usage:
# scanner = AdvancedSecurityScanner('192.168.1.1', '1-1024')
# scanner.add_vulnerability_check(check_ssh_version)
# scanner.run_scans()