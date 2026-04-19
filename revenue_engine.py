import json
import os
from datetime import datetime
from pathlib import Path

class RevenueEngine:
    def __init__(self, base_path="data/revenue"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.target = 1_000_000_000_000  # $1 Trillion
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
            json.dump({
                'current': self.current,
                'target': self.target,
                'last_updated': datetime.utcnow().isoformat()
            }, f, indent=2)
    
    def record_revenue(self, amount: float, source: str, builder: str):
        self.current += amount
        self.save_state()
        
        # Log transaction
        tx_file = self.base_path / "transactions.json"
        if tx_file.exists():
            with open(tx_file, 'r') as f:
                txs = json.load(f)
        else:
            txs = []
        
        txs.append({
            "timestamp": datetime.utcnow().isoformat(),
            "amount": amount,
            "source": source,
            "builder": builder,
            "cumulative": self.current
        })
        
        with open(tx_file, 'w') as f:
            json.dump(txs, f, indent=2)
        
        return {
            "added": amount,
            "cumulative": self.current,
            "remaining": self.target - self.current,
            "percent_complete": (self.current / self.target) * 100 if self.target > 0 else 0
        }
    
    def get_status(self):
        return {
            "target": self.target,
            "current": self.current,
            "remaining": self.target - self.current,
            "percent": (self.current / self.target) * 100 if self.target > 0 else 0,
            "target_met": self.current >= self.target
        }

# Singleton instance
revenue_engine = RevenueEngine()
status = revenue_engine.get_status()
print(f"💰 Revenue target: ${status['target']:,.0f}")
print(f"📊 Current: ${status['current']:,.2f}")
print(f"🎯 Remaining: ${status['remaining']:,.0f}")
print(f"📈 Progress: {status['percent']:.10f}%")
