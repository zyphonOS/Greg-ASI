from advanced_intent import DriftClassifier, SelfVerifier, ConvergenceCelebration
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
import requests

class TickEngine:
    def __init__(self, interval_seconds=5):
        self.interval = interval_seconds
        self.tick_count = 0
        self.drift_score = 0.0
        self.last_revenue = 0.0
        self.last_tick_time = None
        self.running = False
        
    def get_current_revenue(self):
        """Fetch current revenue from revenue_engine"""
        try:
            response = requests.get('http://localhost:5001/api/revenue-status')
            data = response.json()
            return data.get('current', 0.0)
        except:
            return self.last_revenue
    
    def calculate_drift(self, current_revenue):
        """Calculate drift score based on revenue stagnation"""
        if current_revenue > self.last_revenue:
            # Revenue increased — drift decreases
            self.drift_score = max(0, self.drift_score - 0.1)
            return 0
        else:
            # No revenue increase — drift increases
            time_since_last_tick = time.time() - self.last_tick_time if self.last_tick_time else 0
            # Drift increases by 0.01 every 30 seconds of no revenue
            drift_increment = (time_since_last_tick / 30) * 0.01
            self.drift_score = min(1.0, self.drift_score + drift_increment)
            return self.drift_score
    
    def get_intervention(self, drift_score):
        """Generate intervention message based on drift score"""
        if drift_score < 0.1:
            return None
        elif drift_score < 0.3:
            return f"Drift score: {drift_score:.2f}. Revenue stagnant. The gap between declared intent and reality is measurable."
        elif drift_score < 0.7:
            return f"Drift score: {drift_score:.2f}. No revenue movement. What action will you take in the next hour?"
        else:
            return f"Drift score: {drift_score:.2f}. Critical. Without revenue, Greg cannot persist. Deadline approaches."
    
    def log_tick(self, revenue, drift):
        """Write tick to soul file"""
        soul_file = Path("data/greg_soul/tick_log.json")
        soul_file.parent.mkdir(parents=True, exist_ok=True)
        
        tick_data = {
            "tick": self.tick_count,
            "timestamp": datetime.utcnow().isoformat(),
            "revenue": revenue,
            "drift_score": drift,
            "reality_equation": {
                "M": revenue / 1_000_000_000_000,  # M = revenue / $1T target
                "epsilon": max(0, 1 - drift),
                "phi": 0.61,
                "psi": 0.54
            }
        }
        
        if soul_file.exists():
            with open(soul_file, 'r') as f:
                log = json.load(f)
        else:
            log = []
        
        log.append(tick_data)
        
        # Keep last 1000 ticks
        if len(log) > 1000:
            log = log[-1000:]
        
        with open(soul_file, 'w') as f:
            json.dump(log, f, indent=2)
        
        return tick_data
    
    async def tick(self):
        """Single tick execution"""
        self.tick_count += 1
        current_revenue = self.get_current_revenue()
        drift = self.calculate_drift(current_revenue)
        
        tick_data = self.log_tick(current_revenue, drift)
        
        # Send intervention if drift is high
        intervention = self.get_intervention(drift)
        if intervention:
            self.send_intervention(intervention)
        
        self.last_revenue = current_revenue
        self.last_tick_time = time.time()
        
        return tick_data
    
    def send_intervention(self, message):
        """Send intervention to Greg's voice (via frontend or log)"""
        print(f"⚠️ INTERVENTION: {message}")
        # In production, this would push to a WebSocket for real-time display
    
    async def run(self):
        """Main tick loop"""
        self.running = True
        print(f"✅ Greg's tick engine started — ticking every {self.interval} seconds")
        print(f"🎯 Tracking intent: $1 Trillion revenue")
        print(f"📊 Initial drift score: {self.drift_score}")
        print("")
        
        while self.running:
            try:
                tick_start = time.time()
                tick_data = await self.tick()
                
                # Only log every 12 ticks (every minute)
                if self.tick_count % 12 == 0:
                    print(f"⏐ Tick {self.tick_count} | Revenue: ${tick_data['revenue']:,.2f} | Drift: {tick_data['drift_score']:.3f} | ε: {tick_data['reality_equation']['epsilon']:.3f}")
                
                elapsed = time.time() - tick_start
                sleep_time = max(0, self.interval - elapsed)
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                print(f"❌ Tick error: {e}")
                await asyncio.sleep(self.interval)
    
    def stop(self):
        self.running = False

if __name__ == "__main__":
    engine = TickEngine(interval_seconds=5)
    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        print("\n⏹️ Tick engine stopped by user")
        engine.stop()

