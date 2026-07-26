
class DomainAnalysis:
    def __init__(self, requirements, needs):
        self.requirements = requirements
        self.needs = needs

    def get_requirements(self):
        return self.requirements

    def get_needs(self):
        return self.needs


class NewAgentSpecialistGenerator:
    def __init__(self, domain_analysis):
        self.domain_analysis = domain_analysis

    def generate_specialist(self):
        requirements = self.domain_analysis.get_requirements()
        needs = self.domain_analysis.get_needs()
        specialist = Specialist(requirements, needs)
        return specialist


class Specialist:
    def __init__(self, requirements, needs):
        self.requirements = requirements
        self.needs = needs

    def __str__(self):
        return f"Specialist with requirements {self.requirements} and needs {self.needs}"


# Example usage
requirements = ["Requirement1", "Requirement2"]
needs = ["Need1", "Need2"]
domain_analysis = DomainAnalysis(requirements, needs)
generator = NewAgentSpecialistGenerator(domain_analysis)
specialist = generator.generate_specialist()
print(specialist)
