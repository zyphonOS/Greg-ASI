#!/usr/bin/env python3
import os
import sys
import requests
from pathlib import Path

BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
ROUTES = ['/', '/pikkaio', '/truth', '/dashboard', '/revenue', '/zyphonos', '/treasury',]
STATIC_FILES = [
    'static/css/base.css', 'static/js/base.js',
    'static/css/homepage.css', 'static/js/homepage.js',
    'static/css/pikkaio.css', 'static/js/pikkaio.js',
    'static/css/truth.css', 'static/js/truth.js',
    'static/css/dashboard.css', 'static/js/dashboard.js',
    'static/css/revenue.css', 'static/js/revenue.js'
]

def check_routes():
    print("Checking routes...")
    for route in ROUTES:
        try:
            resp = requests.get(f"{BASE_URL}{route}", timeout=5)
            assert resp.status_code == 200, f"{route} returned {resp.status_code}"
            assert 'JetBrains Mono' in resp.text or 'base.css' in resp.text, f"{route} missing font or base.css"
            print(f"  ✓ {route}")
        except Exception as e:
            print(f"  ✗ {route}: {e}")
            return False
    return True

def check_static_files():
    print("Checking static files...")
    missing = []
    for f in STATIC_FILES:
        if not Path(f).exists():
            missing.append(f)
    if missing:
        print(f"  ✗ Missing: {', '.join(missing)}")
        return False
    print("  ✓ All static files present")
    return True

def main():
    print("=== Frontend Rebuild Verification ===\n")
    ok = check_routes() and check_static_files()
    if ok:
        print("\n✅ All checks passed. Frontend is BOUNDED.")
        sys.exit(0)
    else:
        print("\n❌ Verification failed.")
        sys.exit(1)

if __name__ == '__main__':
    main()
