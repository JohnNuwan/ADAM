
import random
import time

class SecurityScanner:
    def __init__(self):
        self.vulnerabilities = []

    def scan(self, system):
        print("Scanning system...")
        time.sleep(2)  # Simulate scanning time
        self.vulnerabilities = [random.choice([True, False]) for _ in range(5)]
        return self.vulnerabilities

class AutomatedIntrusionTester:
    def __init__(self):
        self.scanner = SecurityScanner()
        self.system_vulnerable = False

    def test_system(self, system):
        vulnerabilities = self.scanner.scan(system)
        self.system_vulnerable = any(vulnerabilities)
        if self.system_vulnerable:
            print("Vulnerabilities detected!")
            self.correct_vulnerabilities(vulnerabilities)

    def correct_vulnerabilities(self, vulnerabilities):
        for idx, vulnerable in enumerate(vulnerabilities):
            if vulnerable:
                print(f"Correcting vulnerability at index {idx}...")
                time.sleep(1)  # Simulate correction time
                vulnerabilities[idx] = False
                print(f"Vulnerability at index {idx} corrected.")
        print("All vulnerabilities corrected.")

if __name__ == "__main__":
    tester = AutomatedIntrusionTester()
    system_to_test = "example_system"
    tester.test_system(system_to_test)
