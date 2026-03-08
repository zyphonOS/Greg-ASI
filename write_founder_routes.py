import ast

# Write greg_exosuit.py standalone first
exosuit = open('/workspaces/Greg-ASI/write_founder_module.py', 'w')
exosuit.write("""
import json, os
from pathlib import Path

ROOT = Path(__file__).parent
FOUNDER_PROFILE_PATH = ROOT / "data" / "ebuka_profile.json"

def get_founder_profile():
    try:
        with open(FOUNDER_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def update_founder_profile(data):
    profile = get_founder_profile()
    for key, val in data.items():
        if isinstance(val, dict) and isinstance(profile.get(key), dict):
            profile[key].update(val)
        else:
            profile[key] = val
    with open(FOUNDER_PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    return profile
""")
exosuit.close()

# Verify syntax
ast.parse(open('/workspaces/Greg-ASI/write_founder_module.py').read())
print("module syntax valid")

# Now wire into api.py with single import
api_path = '/workspaces/Greg-ASI/interface/api.py'
content = open(api_path, encoding='utf-8').read()

# Add import after BASE_DIR definition
old_import = 'BASE_DIR = os.path.dirname(os.path.abspath(__file__))'
new_import = '''BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Founder profile
FOUNDER_PROFILE_PATH = os.path.join(BASE_DIR, "..", "data", "ebuka_profile.json")

def get_founder_profile():
    try:
        with open(FOUNDER_PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}'''

if 'get_founder_profile' not in content:
    content = content.replace(old_import, new_import)
    print("get_founder_profile added")
else:
    print("get_founder_profile already present")

# Add routes before agents route
routes = '''
# -----------------------------------------
# GET /api/founder/profile
# -----------------------------------------
@app.route("/api/founder/profile")
def founder_profile():
    return jsonify(get_founder_profile())

# -----------------------------------------
# POST /api/founder/update
# -----------------------------------------
@app.route("/api/founder/update", methods=["POST"])
def founder_update():
    try:
        data = request.get_json()
        profile = get_founder_profile()
        for key, val in data.items():
            if isinstance(val, dict) and isinstance(profile.get(key), dict):
                profile[key].update(val)
            else:
                profile[key] = val
        with open(FOUNDER_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        return jsonify({"status": "updated", "profile": profile})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

'''

marker = '# -----------------------------------------\n# GET /api/world/agents'
if '/api/founder/profile' not in content:
    content = content.replace(marker, routes + marker)
    print("founder routes added")
else:
    print("founder routes already present")

try:
    ast.parse(content)
    open(api_path, 'w', encoding='utf-8').write(content)
    print("SUCCESS - syntax valid - saved")
except SyntaxError as e:
    print(f"SYNTAX ERROR line {e.lineno}: {e.msg}")
