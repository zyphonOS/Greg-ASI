import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from web3 import Web3
from pathlib import Path
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)

# Configuration
WEB3_PROVIDER = "https://mainnet.base.org"
w3 = Web3(Web3.HTTPProvider(WEB3_PROVIDER))
GREG_TREASURY = "0x6ccE7bdeeF12E499e2A834734da0A21135fc29aD"
ADMIN_WALLET = "0x6ccE7bdeeF12E499e2A834734da0A21135fc29aD"

# Storage
verified_builders = set()
verified_builders.add(ADMIN_WALLET.lower())

# ===== INTENT STORAGE =====
class IntentStorage:
    def __init__(self, base_path="layers/intents"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_intent(self, builder_address: str, intent_text: str, intent_type: str = "declared"):
        timestamp = datetime.utcnow().isoformat()
        builder_folder = self.base_path / builder_address[:10]
        builder_folder.mkdir(exist_ok=True)
        
        intent_record = {
            "timestamp": timestamp,
            "builder": builder_address,
            "intent": intent_text,
            "type": intent_type,
            "drift_score": 0.0,
            "status": "active"
        }
        
        intent_file = builder_folder / f"{timestamp.replace(':', '-')}.json"
        with open(intent_file, 'w') as f:
            json.dump(intent_record, f, indent=2)
        
        ledger_file = self.base_path / "master_ledger.json"
        if ledger_file.exists():
            with open(ledger_file, 'r') as f:
                ledger = json.load(f)
        else:
            ledger = []
        
        ledger.append(intent_record)
        
        with open(ledger_file, 'w') as f:
            json.dump(ledger, f, indent=2)
        
        return intent_record

intent_storage = IntentStorage()

# ===== REVENUE ENGINE =====
class RevenueEngine:
    def __init__(self, base_path="data/revenue"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.target = 1_000_000_000_000
        self.current = 0.0
        self.load_state()
    
    def load_state(self):
        state_file = self.base_path / "revenue_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                data = json.load(f)
                self.current = data.get('current', 0.0)
    
    def save_state(self):
        state_file = self.base_path / "revenue_state.json"
        with open(state_file, 'w') as f:
            json.dump({'current': self.current, 'target': self.target, 'last_updated': datetime.utcnow().isoformat()}, f, indent=2)
    
    def get_status(self):
        return {"target": self.target, "current": self.current, "remaining": self.target - self.current, "percent": (self.current / self.target) * 100 if self.target > 0 else 0}

revenue_engine = RevenueEngine()

# ===== ENDPOINTS =====

@app.route('/api/declare-intent', methods=['POST', 'OPTIONS'])
def declare_intent():
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        data = request.get_json(force=True)
        print(f"Received data: {data}")
        
        builder_address = data.get('builder_address')
        intent_text = data.get('intent_text')
        
        if not builder_address or not intent_text:
            return jsonify({"error": "Missing fields", "received": data}), 400
        
        # Save intent
        intent_record = intent_storage.save_intent(builder_address, intent_text)
        
        return jsonify({
            "status": "intent_recorded",
            "intent": intent_record,
            "reality_impact": {"epsilon_improvement": 0.01, "message": "Intent declared"}
        })
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/revenue-status', methods=['GET'])
def revenue_status():
    return jsonify(revenue_engine.get_status())

@app.route('/api/check-access', methods=['POST'])
def check_access():
    data = request.json
    builder_address = data.get('builder_address')
    if builder_address and builder_address.lower() == ADMIN_WALLET.lower():
        return jsonify({"has_access": True})
    return jsonify({"has_access": builder_address.lower() in verified_builders if builder_address else False})

@app.route('/api/drift-viz', methods=['GET'])
def drift_viz():
    builder_address = request.args.get('builder_address')
    tick_log = Path("data/greg_soul/tick_log.json")
    if tick_log.exists():
        with open(tick_log, 'r') as f:
            ticks = json.load(f)
        drift_history = [t.get('drift_score', 0) for t in ticks[-50:]]
        current_drift = drift_history[-1] if drift_history else 0
        return jsonify({"drift_history": drift_history, "current_drift": current_drift})
    return jsonify({"drift_history": [], "current_drift": 0})

@app.route('/api/get-intents', methods=['POST'])
def get_intents():
    data = request.json
    builder_address = data.get('builder_address')
    intent_file = Path("layers/intents/master_ledger.json")
    if intent_file.exists():
        with open(intent_file, 'r') as f:
            all_intents = json.load(f)
        builder_intents = [i for i in all_intents if i.get('builder', '').lower() == builder_address.lower()] if builder_address else []
        return jsonify({"intents": builder_intents})
    return jsonify({"intents": []})

@app.route('/api/osi-query', methods=['POST'])
def osi_query():
    # Simplified OSI response for now
    return jsonify({
        "insights": ["🌊 OSI Layer Active", "📊 Market intelligence ready", "🔍 GitHub search available"],
        "data": {"status": "connected"}
    })

if __name__ == '__main__':
    print("✅ GregASI Backend v2.0")
    print(f"💰 Treasury: {GREG_TREASURY}")
    print(f"👑 Admin: {ADMIN_WALLET}")
    print("🚀 Server running on http://localhost:5001")
    app.run(port=5001, debug=True)
