from .ir_parser import IRParser
from .asm_parser import ASMParser

# Backwards compatibility - keep old function names
def analyze_ir(filename: str, skip_patterns=None):
    """Backwards-compatible wrapper for IRParser."""
    return IRParser().parse(filename, skip_patterns=skip_patterns)

def analyze_asm(filename: str, skip_prefixes=None, mode: str = "counts"):
    """Backwards-compatible wrapper for ASMParser."""
    functions = ASMParser().parse(filename, skip_prefixes=skip_prefixes)
    if mode == "functions":
        return functions
    num_functions = len(functions)
    function_names = list(functions.keys())
    num_basic_blocks = sum(fn.blocks for fn in functions.values())
    num_instructions = sum(fn.total_instructions for fn in functions.values())
    return num_functions, num_basic_blocks, num_instructions, function_names
