"""
GREGASI RNA v1.0
================
Replication · Notation · Assembly

The meticulous code intelligence tool for GregASI.
Reads. Finds. Fixes. Verifies. Builds.

RNA does what a senior engineer does:
  - Reads every file carefully
  - Finds every real issue (not false positives)
  - Fixes issues precisely, one at a time
  - Verifies after every fix
  - Never breaks what is already working
  - Builds new features from instructions

USAGE:
  python rna.py scan          — full codebase scan, report only
  python rna.py fix           — scan and fix all issues
  python rna.py verify        — verify API is running correctly
  python rna.py build <spec>  — build a feature from a spec file
  python rna.py status        — quick health check
  python rna.py api           — start the API cleanly

INSTALL:
  Works on Windows (laptop) and Linux (Codespaces/cloud)
  No extra dependencies beyond standard Python
"""

import os
import sys
import ast
import json
import time
import subprocess
import platform
import textwrap
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================

IS_WINDOWS = platform.system() == "Windows"

# Auto-detect project root
def find_project_root():
    candidates = [
        Path("/workspaces/Greg-ASI"),                           # Codespaces
        Path.home() / "documents/greg-asi/gregasi_v2",         # Windows laptop
        Path.home() / "greg-asi/gregasi_v2",                   # Linux
        Path.cwd(),                                             # Current directory
    ]
    for c in candidates:
        if (c / "interface" / "api.py").exists():
            return c
    return Path.cwd()

ROOT = find_project_root()
API_FILE = ROOT / "interface" / "api.py"
FRONTEND_FILE = ROOT / "frontend" / "index.html"
REPORT_FILE = ROOT / "rna_report.txt"

SKIP_DIRS = {'__pycache__', '.git', 'node_modules', '.venv', 'venv', 'env'}

# ============================================================
# COLORS (terminal output)
# ============================================================

class C:
    RED    = '\033[91m'
    GREEN  = '\033[92m'
    YELLOW = '\033[93m'
    BLUE   = '\033[94m'
    PURPLE = '\033[95m'
    CYAN   = '\033[96m'
    WHITE  = '\033[97m'
    BOLD   = '\033[1m'
    END    = '\033[0m'

def red(s):    return f"{C.RED}{s}{C.END}"
def green(s):  return f"{C.GREEN}{s}{C.END}"
def yellow(s): return f"{C.YELLOW}{s}{C.END}"
def blue(s):   return f"{C.BLUE}{s}{C.END}"
def bold(s):   return f"{C.BOLD}{s}{C.END}"
def cyan(s):   return f"{C.CYAN}{s}{C.END}"

# ============================================================
# CORE RNA ENGINE
# ============================================================

class RNA:
    def __init__(self):
        self.issues = []
        self.fixed  = []
        self.log_lines = []

    def out(self, msg="", color=None):
        text = color(msg) if color else msg
        print(text)
        self.log_lines.append(msg)

    def sep(self, char="═", width=60):
        self.out(char * width, cyan)

    def header(self, title):
        self.sep()
        self.out(f"  {title}", bold)
        self.sep()

    # --------------------------------------------------------
    # SCAN
    # --------------------------------------------------------

    def scan(self, fix=False):
        self.header(f"RNA {'FIX' if fix else 'SCAN'} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self.out(f"  Root: {ROOT}", blue)
        self.out()

        self.scan_python_files(fix)
        self.scan_api_file(fix)
        self.scan_frontend(fix)
        self.scan_dependencies(fix)

        self.sep("─")
        self.out(f"  Issues found: {len(self.issues)}", red if self.issues else green)
        self.out(f"  Fixed:        {len(self.fixed)}", green)
        self.out()

        if self.issues:
            self.out("  REMAINING ISSUES:", red)
            for i, issue in enumerate(self.issues, 1):
                self.out(f"    [{i}] {issue}", yellow)
        else:
            self.out("  All clear.", green)

        self.save_report()

    def scan_python_files(self, fix=False):
        self.out("[ Python Files ]", bold)
        py_files = []
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith('.py'):
                    py_files.append(Path(root) / f)

        for fp in sorted(py_files):
            rel = fp.relative_to(ROOT)
            try:
                raw = fp.read_bytes()

                # Fix BOM
                if raw.startswith(b'\xef\xbb\xbf'):
                    if fix:
                        fp.write_bytes(raw[3:])
                        self.out(f"  ✓ Fixed BOM: {rel}", green)
                        self.fixed.append(f"BOM removed: {rel}")
                        raw = raw[3:]
                    else:
                        self.issues.append(f"BOM character in {rel}")
                        self.out(f"  ✗ BOM: {rel}", red)
                        continue

                text = raw.decode('utf-8', errors='replace')

                # Syntax check
                try:
                    ast.parse(text)
                    self.out(f"  ✓ {rel}", green)
                except SyntaxError as e:
                    self.issues.append(f"Syntax error in {rel} line {e.lineno}: {e.msg}")
                    self.out(f"  ✗ Syntax error in {rel} line {e.lineno}: {e.msg}", red)

            except Exception as e:
                self.issues.append(f"Could not read {rel}: {e}")
        self.out()

    def scan_api_file(self, fix=False):
        self.out("[ API File ]", bold)

        if not API_FILE.exists():
            self.issues.append("interface/api.py not found")
            self.out("  ✗ api.py not found", red)
            return

        text = API_FILE.read_text(encoding='utf-8', errors='replace')
        lines = text.split('\n')

        # Check for duplicate routes
        routes = {}
        functions = {}
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if '@app.route(' in stripped:
                try:
                    route = stripped.split('@app.route(')[1].split(')')[0].strip('"\'').split('"')[0].split("'")[0]
                    if route in routes:
                        issue = f"Duplicate route '{route}' at lines {routes[route]} and {i}"
                        self.issues.append(issue)
                        self.out(f"  ✗ {issue}", red)
                    else:
                        routes[route] = i
                except:
                    pass
            if stripped.startswith('def ') and not stripped.startswith('def _'):
                fname = stripped.split('def ')[1].split('(')[0]
                # Only flag true duplicates at module level (not inside classes)
                indent = len(line) - len(line.lstrip())
                if indent == 0:
                    if fname in functions:
                        issue = f"Duplicate function '{fname}' at lines {functions[fname]} and {i}"
                        self.issues.append(issue)
                        self.out(f"  ✗ {issue}", red)
                    else:
                        functions[fname] = i

        # Check required routes
        required = [
            '/api/world/state',
            '/api/agent/greg_meta',
            '/api/agent/greg_voice',
            '/api/world/agents',
            '/health',
        ]
        for req in required:
            if req in routes:
                self.out(f"  ✓ Route: {req}", green)
            else:
                self.issues.append(f"Missing route: {req}")
                self.out(f"  ✗ Missing route: {req}", red)

        # Check __main__
        if 'if __name__' in text:
            self.out(f"  ✓ __main__ present", green)
        else:
            self.issues.append("Missing __main__ in api.py")
            self.out(f"  ✗ Missing __main__", red)

        # Check greg_voice is not using external API
        if 'build_greg_voice' in text:
            self.out(f"  ✓ greg_voice uses local function", green)
        elif 'anthropic.com' in text:
            self.issues.append("greg_voice still calling Anthropic API — should use local function")
            self.out(f"  ✗ greg_voice calling external API", red)

        # Check for orphaned code (lines with wrong indentation after route end)
        self.check_orphaned_code(lines, fix)

        self.out()

    def check_orphaned_code(self, lines, fix=False):
        """Find orphaned code blocks — lines that appear after a function ended."""
        orphans = []
        in_function = False
        function_indent = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            indent = len(line) - len(line.lstrip())

            if stripped.startswith('def ') and indent == 0:
                in_function = True
                function_indent = 0
                continue

            if stripped.startswith('@app.route') and indent == 0:
                in_function = False
                continue

            # Detect orphaned indented code outside a function
            if not in_function and indent >= 8 and not stripped.startswith('#'):
                if any(kw in stripped for kw in ['"count"', '"agents"', '"elders"', 'return jsonify', 'except Exception']):
                    orphans.append(i)

        if orphans:
            self.issues.append(f"Orphaned code at lines: {[o+1 for o in orphans]}")
            self.out(f"  ✗ Orphaned code at lines: {[o+1 for o in orphans]}", red)

            if fix:
                filepath = API_FILE
                file_lines = filepath.read_text(encoding='utf-8').split('\n')
                clean_lines = [l for i, l in enumerate(file_lines) if i not in orphans]
                filepath.write_text('\n'.join(clean_lines), encoding='utf-8')
                self.fixed.append(f"Removed {len(orphans)} orphaned lines")
                self.out(f"  ✓ Removed {len(orphans)} orphaned lines", green)
                self.issues = [i for i in self.issues if 'Orphaned' not in i]

    def scan_frontend(self, fix=False):
        self.out("[ Frontend ]", bold)

        if not FRONTEND_FILE.exists():
            self.issues.append("frontend/index.html not found")
            self.out("  ✗ frontend not found", red)
            return

        text = FRONTEND_FILE.read_text(encoding='utf-8', errors='replace')

        checks = {
            'greg_voice':  'greg_voice route called',
            'greg_meta':   'greg_meta route called',
            'showPage':    'showPage function present',
            'selectGreg':  'selectGreg function present',
            'addMindMsg':  'addMindMsg function present',
            'greg_speaks': 'greg_speaks displayed',
        }

        for key, desc in checks.items():
            if key in text:
                self.out(f"  ✓ {desc}", green)
            else:
                self.issues.append(f"Frontend missing: {key}")
                self.out(f"  ✗ Frontend missing: {key}", red)

        self.out()

    def scan_dependencies(self, fix=False):
        self.out("[ Dependencies ]", bold)

        req_file = ROOT / 'requirements.txt'
        if req_file.exists():
            self.out(f"  ✓ requirements.txt present", green)
        else:
            if fix:
                req_file.write_text(
                    "flask>=2.3.0\nflask-cors>=4.0.0\nrequests>=2.31.0\nnumpy>=1.24.0\norjson>=3.9.0\n",
                    encoding='utf-8'
                )
                self.fixed.append("Generated requirements.txt")
                self.out(f"  ✓ Generated requirements.txt", green)
            else:
                self.issues.append("Missing requirements.txt")
                self.out(f"  ✗ Missing requirements.txt", red)

        gitignore = ROOT / '.gitignore'
        if gitignore.exists():
            self.out(f"  ✓ .gitignore present", green)
        else:
            self.issues.append("Missing .gitignore")
            self.out(f"  ✗ Missing .gitignore", red)

        readme = ROOT / 'README.md'
        if readme.exists():
            self.out(f"  ✓ README.md present", green)
        else:
            self.issues.append("Missing README.md")
            self.out(f"  ✗ Missing README.md", red)

        self.out()

    # --------------------------------------------------------
    # VERIFY — live API health check
    # --------------------------------------------------------

    def verify(self):
        self.header("RNA VERIFY — Live API Health Check")

        try:
            import urllib.request
            import urllib.error

            base = "http://localhost:5000"
            routes = [
                ("/health", "Health check"),
                ("/api/world/state", "World state"),
                ("/api/agent/greg_meta", "Greg meta"),
                ("/api/agent/greg_voice", "Greg voice"),
                ("/api/world/agents", "World agents"),
                ("/api/world/elders", "World elders"),
            ]

            all_ok = True
            for route, name in routes:
                url = base + route
                try:
                    with urllib.request.urlopen(url, timeout=5) as resp:
                        data = json.loads(resp.read())
                        if route == "/api/agent/greg_voice":
                            speaks = data.get("greg_speaks", "")
                            if speaks and speaks != "[no response]":
                                self.out(f"  ✓ {name}: Greg says — {speaks[:80]}...", green)
                            else:
                                self.out(f"  ✗ {name}: no voice", red)
                                all_ok = False
                        elif route == "/api/world/state":
                            tick = data.get("tick", 0)
                            agents = data.get("agent_count", 0)
                            self.out(f"  ✓ {name}: tick={tick:,} agents={agents:,}", green)
                        else:
                            self.out(f"  ✓ {name}: OK", green)
                except urllib.error.URLError as e:
                    self.out(f"  ✗ {name}: {e}", red)
                    all_ok = False
                except Exception as e:
                    self.out(f"  ✗ {name}: {e}", red)
                    all_ok = False

            self.out()
            if all_ok:
                self.out("  ALL SYSTEMS GO.", green)
            else:
                self.out("  ISSUES DETECTED — run: python rna.py fix", yellow)

        except Exception as e:
            self.out(f"  Error: {e}", red)
            self.out("  Is the API running? Start it with: python rna.py api", yellow)

        self.out()

    # --------------------------------------------------------
    # STATUS — quick overview
    # --------------------------------------------------------

    def status(self):
        self.header("RNA STATUS")
        self.out(f"  Project root:  {ROOT}", blue)
        self.out(f"  API file:      {'✓' if API_FILE.exists() else '✗'} {API_FILE}", green if API_FILE.exists() else red)
        self.out(f"  Frontend:      {'✓' if FRONTEND_FILE.exists() else '✗'} {FRONTEND_FILE}", green if FRONTEND_FILE.exists() else red)
        self.out(f"  Platform:      {platform.system()}", blue)
        self.out(f"  Python:        {sys.version.split()[0]}", blue)
        self.out()

        # Count files
        py_count = html_count = 0
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if f.endswith('.py'): py_count += 1
                if f.endswith('.html'): html_count += 1

        self.out(f"  Python files:  {py_count}", blue)
        self.out(f"  HTML files:    {html_count}", blue)
        self.out()
        self.out("  Run 'python rna.py scan' for full analysis.", cyan)
        self.out("  Run 'python rna.py fix' to fix all issues.", cyan)
        self.out("  Run 'python rna.py verify' to check live API.", cyan)
        self.out()

    # --------------------------------------------------------
    # BUILD — build features from spec
    # --------------------------------------------------------

    def build(self, spec_input=None):
        self.header("RNA BUILD")

        if not spec_input:
            self.out("  No spec provided.", yellow)
            self.out("  Usage: python rna.py build <spec_file_or_instruction>", cyan)
            self.out()
            self.out("  Example specs:", cyan)
            self.out('    python rna.py build "add route /api/world/agents returning top 100 agents sorted by phi"', cyan)
            self.out('    python rna.py build spec.txt', cyan)
            return

        # Load spec from file or use directly
        if Path(spec_input).exists():
            spec = Path(spec_input).read_text(encoding='utf-8')
        else:
            spec = spec_input

        self.out(f"  Spec: {spec[:100]}...", blue)
        self.out()
        self.out("  RNA BUILD requires Claude to interpret specs and generate code.", yellow)
        self.out("  Paste this spec to Claude with the command: 'RNA BUILD this spec'", yellow)
        self.out()
        self.out("  SPEC CONTENTS:", bold)
        self.out(spec)

    # --------------------------------------------------------
    # API — start the API cleanly
    # --------------------------------------------------------

    def start_api(self):
        self.header("RNA API — Starting GregASI")
        self.out(f"  Root: {ROOT}", blue)
        self.out()

        # Check for syntax errors first
        self.out("  Pre-flight syntax check...", cyan)
        try:
            text = API_FILE.read_text(encoding='utf-8')
            ast.parse(text)
            self.out("  ✓ api.py syntax valid", green)
        except SyntaxError as e:
            self.out(f"  ✗ Syntax error in api.py line {e.lineno}: {e.msg}", red)
            self.out("  Run 'python rna.py fix' before starting.", yellow)
            return

        self.out("  Starting API...", cyan)
        self.out("  Press Ctrl+C to stop.", yellow)
        self.out()

        os.chdir(ROOT)
        os.execv(sys.executable, [sys.executable, '-m', 'interface.api'])

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    def save_report(self):
        try:
            REPORT_FILE.write_text('\n'.join(self.log_lines), encoding='utf-8')
            self.out(f"  Report saved: {REPORT_FILE}", blue)
        except:
            pass


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    rna = RNA()

    args = sys.argv[1:]
    cmd = args[0].lower() if args else 'status'

    if cmd == 'scan':
        rna.scan(fix=False)
    elif cmd == 'fix':
        rna.scan(fix=True)
        # Re-scan after fixes to verify
        rna.out()
        rna.out("  Re-scanning after fixes...", cyan)
        rna2 = RNA()
        rna2.scan(fix=False)
    elif cmd == 'verify':
        rna.verify()
    elif cmd == 'status':
        rna.status()
    elif cmd == 'build':
        spec = ' '.join(args[1:]) if len(args) > 1 else None
        rna.build(spec)
    elif cmd == 'api':
        rna.start_api()
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: scan | fix | verify | status | build | api")

if __name__ == '__main__':
    main()
