import json
import os
from datetime import datetime
from pathlib import Path

class IntentStorage:
    def __init__(self, base_path="layers/intents"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_intent(self, builder_address: str, intent_text: str, intent_type: str = "declared"):
        """Save a declared intent to the filesystem"""
        timestamp = datetime.utcnow().isoformat()
        
        # Create builder-specific folder
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
        
        # Save individual intent file
        intent_file = builder_folder / f"{timestamp.replace(':', '-')}.json"
        with open(intent_file, 'w') as f:
            json.dump(intent_record, f, indent=2)
        
        # Append to master ledger
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
    
    def get_builder_intents(self, builder_address: str):
        """Retrieve all intents for a specific builder"""
        builder_folder = self.base_path / builder_address[:10]
        if not builder_folder.exists():
            return []
        
        intents = []
        for intent_file in builder_folder.glob("*.json"):
            with open(intent_file, 'r') as f:
                intents.append(json.load(f))
        
        return sorted(intents, key=lambda x: x['timestamp'])
    
    def update_drift_score(self, builder_address: str, intent_text: str, drift_score: float):
        """Update drift score for the most recent matching intent"""
        builder_folder = self.base_path / builder_address[:10]
        if not builder_folder.exists():
            return None
        
        # Find most recent intent with matching text
        intent_files = sorted(builder_folder.glob("*.json"), reverse=True)
        for intent_file in intent_files:
            with open(intent_file, 'r') as f:
                intent = json.load(f)
            if intent['intent'] == intent_text:
                intent['drift_score'] = drift_score
                intent['status'] = "drifting" if drift_score > 0.3 else "active"
                with open(intent_file, 'w') as f:
                    json.dump(intent, f, indent=2)
                return intent
        
        return None

# Singleton instance
intent_storage = IntentStorage()
