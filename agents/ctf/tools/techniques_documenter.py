
class TechniqueDocumenter:
    def __init__(self):
        self.techniques = []

    def add_technique(self, technique_name, description):
        self.techniques.append({"name": technique_name, "description": description})

    def list_techniques(self):
        for technique in self.techniques:
            print(f"Technique: {technique['name']}, Description: {technique['description']}")

    def save_to_file(self, filename):
        with open(filename, 'w') as file:
            for technique in self.techniques:
                file.write(f"{technique['name']}: {technique['description']}\n")


if __name__ == '__main__':
    doc = TechniqueDocumenter()
    doc.add_technique("Binary Search", "Searches for an element in a sorted array.")
    doc.add_technique("Dynamic Programming", "Solves problems by combining the solutions of subproblems.")
    doc.list_techniques()
    doc.save_to_file('techniques.txt')
