import os
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser
from typing import List, Dict, Any, Optional

PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())

EXT_TO_LANG = {
    '.py': PY_LANGUAGE,
    '.js': JS_LANGUAGE,
    '.jsx': JS_LANGUAGE,
    '.ts': JS_LANGUAGE, # Fallback, though TS has its own parser usually, JS parser works for simple extraction often
    '.tsx': JS_LANGUAGE,
}

EXT_TO_NAME = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
}

def detect_language(file_path: str) -> Optional[str]:
    ext = os.path.splitext(file_path)[1].lower()
    return EXT_TO_NAME.get(ext)

def parse_file(file_path: str) -> List[Dict[str, Any]]:
    """Parse file and extract symbols using tree-sitter."""
    ext = os.path.splitext(file_path)[1].lower()
    lang = EXT_TO_LANG.get(ext)
    
    if not lang:
        return []

    parser = Parser(lang)
    
    with open(file_path, 'rb') as f:
        source_code = f.read()

    tree = parser.parse(source_code)
    symbols = []

    def traverse(node):
        if node.type in ['function_definition', 'class_definition', 'method_definition', 'function_declaration', 'class_declaration', 'method_definition']:
            name_node = None
            for child in node.children:
                if child.type == 'identifier':
                    name_node = child
                    break
            
            if name_node:
                symbol_type = 'function'
                if 'class' in node.type:
                    symbol_type = 'class'
                elif 'method' in node.type:
                    symbol_type = 'method'
                    
                name = source_code[name_node.start_byte:name_node.end_byte].decode('utf8')
                signature = source_code[node.start_byte:node.end_byte].decode('utf8').split('\n')[0]
                
                symbols.append({
                    'name': name,
                    'type': symbol_type,
                    'signature': signature[:255], # Truncate to avoid too long strings
                    'start_line': node.start_point[0] + 1,
                    'end_line': node.end_point[0] + 1
                })
        
        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return symbols


def extract_imports(file_path: str) -> List[str]:
    """Extract imported module names from supported source files."""
    ext = os.path.splitext(file_path)[1].lower()
    lang = EXT_TO_LANG.get(ext)

    if not lang:
        return []

    parser = Parser(lang)
    with open(file_path, 'rb') as f:
        source_code = f.read()

    tree = parser.parse(source_code)
    imports = []

    def node_text(node):
        return source_code[node.start_byte:node.end_byte].decode('utf8')

    def add_import(value):
        value = value.strip().strip('"\'')
        if value and value not in imports:
            imports.append(value)

    def traverse(node):
        if node.type in ['import_statement', 'import_from_statement']:
            source_node = node.child_by_field_name('source')
            if source_node:
                add_import(node_text(source_node))
            else:
                statement = node_text(node)
                if statement.startswith('import '):
                    for imported in statement[7:].split(','):
                        add_import(imported.split(' as ', 1)[0])
                elif statement.startswith('from '):
                    add_import(statement[5:].split(' import ', 1)[0])
        elif node.type == 'call_expression':
            function = node.child_by_field_name('function')
            arguments = node.child_by_field_name('arguments')
            if function and arguments and node_text(function) == 'require':
                argument = arguments.named_children[0] if arguments.named_children else None
                if argument:
                    add_import(node_text(argument))

        for child in node.children:
            traverse(child)

    traverse(tree.root_node)
    return imports
