
import ast
from collections import defaultdict

class ADAMCodeImprovementAgent:
    def __init__(self):
        self.improvement_suggestions = defaultdict(list)

    def analyze_code(self, code):
        tree = ast.parse(code)
        self._analyze_ast(tree)

    def _analyze_ast(self, node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                self.check_function_def(child)
            elif isinstance(child, ast.Import):
                self.check_import(child)
            self._analyze_ast(child)

    def check_function_def(self, node):
        if len(node.body) > 20:
            self.improvement_suggestions[node.name].append("Function is too long, consider splitting it into smaller functions.")
        for n in ast.walk(node):
            if isinstance(n, ast.For):
                self.improvement_suggestions[node.name].append("Consider using list comprehension or map/filter for better readability.")

    def check_import(self, node):
        for alias in node.names:
            if alias.asname:
                self.improvement_suggestions[alias.name].append(f"Import alias {alias.asname} detected, consider using the original name {alias.name} for clarity.")

    def get_improvement_suggestions(self):
        return dict(self.improvement_suggestions)

# Example usage
agent = ADAMCodeImprovementAgent()
code_to_analyze = """
def example_function():
    result = []
    for i in range(100):
        result.append(i * i)
    return result
"""
agent.analyze_code(code_to_analyze)
print(agent.get_improvement_suggestions())
