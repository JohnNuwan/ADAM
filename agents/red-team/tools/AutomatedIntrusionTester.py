from SecurityScanner import AdvancedSecurityScanner


class AutomatedIntrusionTester:
    def __init__(self):
        self.scanner = AdvancedSecurityScanner()

    def scan_and_test(self, target_ip):
        open_ports = self.scanner.scan(target_ip)
        vulnerabilities = self.scanner.detect_vulnerabilities(open_ports)
        return vulnerabilities