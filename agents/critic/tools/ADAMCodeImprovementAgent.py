
import ast
from typing import List, Dict

class ADAMCodeImprovementAgent:
    def __init__(self):
        self.improvement_rules = {
            "unused_import": self.find_unused_imports,
            "repeated_code": self.find_repeated_code_blocks
        }
    
    def audit(self, code: str) -> Dict[str, List[str]]:
        tree = ast.parse(code)
        results = {}
        for rule_name, rule_function in self.improvement_rules.items():
            results[rule_name] = rule_function(tree)
        return results
    
    def find_unused_imports(self, tree: ast.AST) -> List[str]:
        used_names = set()
        unused_imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in used_names:
                        unused_imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    full_name = f"{node.module}.{alias.name}" if node.module else alias.name
                    if full_name not in used_names:
                        unused_imports.append(full_name)
            else:
                if isinstance(node, ast.Name):
                    used_names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    used_names.add(node.attr)
        return unused_imports
    
    def find_repeated_code_blocks(self, tree: ast.AST) -> List[str]:
        repeated_blocks = []
        block_hashes = {}
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.For, ast.While)):
                block_str = ast.unparse(node)
                block_hash = hash(block_str)
                if block_hash in block_hashes:
                    repeated_blocks.append(block_str)
                else:
                    block_hashes[block_hash] = block_str
        
        return repeated_blocks

# Example usage
code_snippet = """
import os
import sys

def test_func():
    print("Hello World")
    print("Hello World")

test_func()
"""

agent = ADAMCodeImprovementAgent()
results = agent.audit(code_snippet)
print(results)
