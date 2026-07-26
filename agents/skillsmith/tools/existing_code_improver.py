
import ast
from ast import NodeTransformer

class CodeImprover(NodeTransformer):
    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        # Add type annotations to function parameters if not present
        for i, arg in enumerate(node.args.args):
            if not arg.annotation:
                arg.annotation = ast.Name(id='Any', ctx=ast.Load())
        return node

    def visit_Call(self, node):
        self.generic_visit(node)
        # Ensure all calls have explicit keyword arguments
        if len(node.keywords) < len(node.args):
            func_name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            function_info = globals().get(func_name, {})
            if callable(function_info) and hasattr(function_info, '__code__'):
                arg_names = function_info.__code__.co_varnames[:function_info.__code__.co_argcount]
                for i, arg in enumerate(node.args):
                    if i >= len(node.keywords):
                        node.keywords.append(ast.keyword(arg=arg_names[i], value=arg))
        return node

def improve_code(code_str):
    tree = ast.parse(code_str)
    improved_tree = CodeImprover().visit(tree)
    return ast.unparse(improved_tree)

# Example usage
original_code = """
def add(a, b):
    return a + b

result = add(1, 2)
"""

improved_code = improve_code(original_code)
print(improved_code)
