
import ast

class ADAMCodeQualityAuditor:
    def __init__(self):
        self._issues = []

    def audit(self, code):
        tree = ast.parse(code)
        self._find_issues(tree)
        return self._issues

    def _find_issues(self, node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                self._check_function_def(child)
            elif isinstance(child, ast.Import) or isinstance(child, ast.ImportFrom):
                self._check_import(child)
            self._find_issues(child)

    def _check_function_def(self, node):
        if len(node.args.args) > 5:
            self._add_issue(f"Function {node.name} has too many arguments (>5).")

    def _check_import(self, node):
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            self._add_issue("Imports from __future__ should be avoided.")

    def _add_issue(self, issue):
        self._issues.append(issue)


# Example usage
if __name__ == "__main__":
    code = """
def example_function(arg1, arg2, arg3, arg4, arg5, arg6):
    import __future__
    print("This is an example function")
"""
    auditor = ADAMCodeQualityAuditor()
    issues = auditor.audit(code)
    for issue in issues:
        print(issue)
