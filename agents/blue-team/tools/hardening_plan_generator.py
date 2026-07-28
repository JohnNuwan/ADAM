
class HardeningPlanGenerator:
    def __init__(self):
        self.vulnerabilities = []

    def add_vulnerability(self, vulnerability):
        self.vulnerabilities.append(vulnerability)

    def generate_hardening_plan(self):
        plan = []
        for vuln in self.vulnerabilities:
            mitigation = self.mitigate_vulnerability(vuln)
            if mitigation:
                plan.append(mitigation)
        return plan

    @staticmethod
    def mitigate_vulnerability(vulnerability):
        if "insecure_deserialization" in vulnerability:
            return "Implement secure deserialization methods and validate all inputs."
        elif "sql_injection" in vulnerability:
            return "Use parameterized queries and validate user input before executing SQL commands."
        elif "xss" in vulnerability:
            return "Sanitize user input and use output encoding to prevent cross-site scripting attacks."
        elif "path_traversal" in vulnerability:
            return "Validate file paths and restrict access to only necessary directories."
        else:
            return None


# Example usage
if __name__ == "__main__":
    generator = HardeningPlanGenerator()
    generator.add_vulnerability("insecure_deserialization")
    generator.add_vulnerability("sql_injection")
    generator.add_vulnerability("unknown_vulnerability")

    plan = generator.generate_hardening_plan()
    for step in plan:
        print(step)
