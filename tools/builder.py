import ast, os, shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent

def _backup(path):
    p = ROOT / path
    backup = str(p) + f".bak.{datetime.now().strftime('%H%M%S')}"
    shutil.copy2(p, backup)
    return backup

def write_new_file(path, content):
    p = ROOT / path
    if p.exists():
        return {"ok": False, "error": f"file already exists: {path}. Use insert or append."}
    try:
        ast.parse(content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError line {e.lineno}: {e.msg}"}
    except:
        pass  # non-python files skip syntax check
    p.parent.mkdir(parents=True, exist_ok=True)
    open(p, 'w', encoding='utf-8').write(content)
    return {"ok": True, "action": "written", "path": str(path)}

def insert_at_line(path, line_no, new_lines):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    backup = _backup(path)
    lines = open(p, encoding='utf-8').readlines()
    idx = line_no - 1
    if idx < 0 or idx > len(lines):
        return {"ok": False, "error": f"line {line_no} out of range (file has {len(lines)} lines)"}
    new_content_lines = lines[:idx] + new_lines + lines[idx:]
    new_content = ''.join(new_content_lines)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError after insert line {e.lineno}: {e.msg}", "backup": backup}
    open(p, 'w', encoding='utf-8').write(new_content)
    return {"ok": True, "action": "inserted", "at_line": line_no, "lines_added": len(new_lines)}

def append_to_file(path, content):
    p = ROOT / path
    if not p.exists():
        return {"ok": False, "error": f"not found: {path}"}
    backup = _backup(path)
    existing = open(p, encoding='utf-8').read()
    new_content = existing + content
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError after append line {e.lineno}: {e.msg}", "backup": backup}
    open(p, 'w', encoding='utf-8').write(new_content)
    return {"ok": True, "action": "appended", "chars_added": len(content)}

def add_flask_route(route_name, route_path, method, function_code, insert_before="# -----------------------------------------\n# Main"):
    api_path = ROOT / "interface" / "api.py"
    if not api_path.exists():
        return {"ok": False, "error": "api.py not found"}
    content = open(api_path, encoding='utf-8').read()
    if route_path in content:
        return {"ok": False, "error": f"route {route_path} already exists"}
    route_block = f"""
# -----------------------------------------
# {method} {route_path}
# -----------------------------------------
@app.route("{route_path}")
def {route_name}():
{function_code}

"""
    marker = "# -----------------------------------------\n# Main"
    if marker not in content:
        return {"ok": False, "error": "Main marker not found in api.py"}
    new_content = content.replace(marker, route_block + marker)
    try:
        ast.parse(new_content)
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError line {e.lineno}: {e.msg}"}
    open(api_path, 'w', encoding='utf-8').write(new_content)
    return {"ok": True, "action": "route added", "route": route_path}
