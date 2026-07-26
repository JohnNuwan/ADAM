
import ast
from typing import List, Tuple

class CodeAuditResult:
    def __init__(self, file_path: str, issues: List[Tuple[str, int]]):
        self.file_path = file_path
        self.issues = issues  # List of tuples (issue_description, line_number)

class ADAMCodeImprovementAgent:
    def __init__(self, audit_results: List[CodeAuditResult]):
        self.audit_results = audit_results

    def parse_code(self, file_path: str) -> ast.AST:
        with open(file_path, 'r') as file:
            code_content = file.read()
        return ast.parse(code_content)

    def suggest_improvements(self) -> List[Tuple[str, str]]:
        improvements = []
        for result in self.audit_results:
            tree = self.parse_code(result.file_path)
            for issue, line_number in result.issues:
                improvement_suggestion = self._generate_improvement(tree, line_number, issue)
                if improvement_suggestion:
                    improvements.append((result.file_path, improvement_suggestion))
        return improvements

    def _generate_improvement(self, tree: ast.AST, line_number: int, issue: str) -> str:
        for node in ast.walk(tree):
            if getattr(node, 'lineno', None) == line_number:
                if isinstance(node, ast.FunctionDef) and "missing-docstring" in issue:
                    return f"Add docstring to function {node.name}"
                elif isinstance(node, ast.Import) and "unused-import" in issue:
                    return f"Remove unused import on line {line_number}"
                elif isinstance(node, ast.Assign) and "redefined-variable" in issue:
                    return f"Rename variable on line {line_number} to avoid redefinition"
        return ""

# Example usage
audit_results = [
    CodeAuditResult('example.py', [('missing-docstring', 10), ('unused-import', 5)]),
]
agent = ADAMCodeImprovementAgent(audit_results)
print(agent.suggest_improvements())
