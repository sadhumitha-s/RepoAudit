import os
import json
try:
    from tree_sitter import Language, Parser
except ModuleNotFoundError:
    # Fallback dummy classes for environments without tree_sitter
    class Language:
        def __init__(self, lib_path: str, language: str):
            raise ImportError('tree_sitter is required for language parsing')
    class Parser:
        def set_language(self, language):
            raise ImportError('tree_sitter is required for parsing')
        def parse(self, source_bytes):
            raise ImportError('tree_sitter is required for parsing')

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_PATH = os.path.join(_ENGINE_DIR, "build", "languages.so")

_R_LANGUAGE = None
_JULIA_LANGUAGE = None

def get_r_parser() -> Parser:
    global _R_LANGUAGE
    if _R_LANGUAGE is None:
        _R_LANGUAGE = Language(_LIB_PATH, 'r')
    parser = Parser()
    parser.set_language(_R_LANGUAGE)
    return parser

def get_julia_parser() -> Parser:
    global _JULIA_LANGUAGE
    if _JULIA_LANGUAGE is None:
        _JULIA_LANGUAGE = Language(_LIB_PATH, 'julia')
    parser = Parser()
    parser.set_language(_JULIA_LANGUAGE)
    return parser

def extract_python_from_ipynb(filepath: str) -> str:
    """Extract and concatenate all python code cells from a Jupyter Notebook."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            notebook = json.load(f)
    except Exception:
        return ""
    
    code_blocks = []
    for cell in notebook.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            if isinstance(source, list):
                code_blocks.append("".join(source))
            elif isinstance(source, str):
                code_blocks.append(source)
    
    return "\n\n".join(code_blocks)
