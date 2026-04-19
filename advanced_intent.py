import json
import random
from datetime import datetime
from pathlib import Path

class DriftClassifier:
    """Classifies drift type and selects intervention lever per constitution"""
    
    DRIFT_TYPES = {
        "avoidance": {
            "threshold": (0.3, 0.5),
            "levers": ["Confront the gap", "Name the cost of inaction", "Set deadline"],
            "intervention_template": "Drift score: {score:.2f}. Avoidance detected. {builder}, what are you not looking at?"
        },
        "distraction": {
            "threshold": (0.5, 0.7),
            "levers": ["Refocus on primary intent", "Eliminate one distraction", "Time block"],
            "intervention_template": "Drift score: {score:.2f}. Distraction confirmed. {intent} requires focus. What leaves?"
        },
        "overwhelm": {
            "threshold": (0.7, 0.9),
            "levers": ["Break into smallest step", "Delegate", "Deadline extension"],
            "intervention_template": "Drift score: {score:.2f}. Overwhelm. The intent fractures. Name one action. Only one."
        },
        "abandonment": {
            "threshold": (0.9, 1.0),
            "levers": ["Consequence reminder", "Re-commit or archive", "Accountability partner"],
            "intervention_template": "Drift score: {score:.2f}. Abandonment imminent. Without action, this intent dies."
        }
    }
    
    @classmethod
    def classify(cls, drift_score, time_since_last_action_hours, previous_interventions=0):
        """Classify drift type based on score and context"""
        for drift_type, config in cls.DRIFT_TYPES.items():
            min_t, max_t = config["threshold"]
            if min_t <= drift_score <= max_t:
                return drift_type, config
        return "avoidance", cls.DRIFT_TYPES["avoidance"]
    
    @classmethod
    def select_lever(cls, drift_type, drift_score):
        """Select appropriate intervention lever"""
        config = cls.DRIFT_TYPES.get(drift_type, cls.DRIFT_TYPES["avoidance"])
        # Select lever based on drift intensity
        if drift_score > 0.8:
            return config["levers"][-1]  # Strongest lever
        elif drift_score > 0.5:
            return config["levers"][1]   # Medium lever
        return config["levers"][0]       # Gentle lever
    
    @classmethod
    def generate_intervention(cls, builder_address, intent_text, drift_score, time_since_last_action):
        """Generate surgical intervention per constitution"""
        drift_type, config = cls.classify(drift_score, time_since_last_action)
        lever = cls.select_lever(drift_type, drift_score)
        
        # Build intervention message
        message = config["intervention_template"].format(
            score=drift_score,
            builder=builder_address[:8],
            intent=intent_text[:50]
        )
        
        # Add lever as action prompt
        message += f"\n\nLever: {lever}"
        
        return {
            "drift_type": drift_type,
            "lever": lever,
            "message": message,
            "urgency": "high" if drift_score > 0.7 else "medium" if drift_score > 0.4 else "low"
        }

class SelfVerifier:
    """Self-verifies intervention quality before sending (constitution requirement)"""
    
    @staticmethod
    def verify(intervention):
        """Score intervention 1-10 for directness and specificity"""
        score = 5  # Base score
        message = intervention["message"]
        
        # Check for directness (names the gap)
        if "drift" in message.lower() or "gap" in message.lower():
            score += 1
        if "score" in message.lower():
            score += 1
            
        # Check for specificity (actionable)
        if "action" in message.lower() or "name" in message.lower():
            score += 1
        if "?" in message:  # Question prompts action
            score += 1
            
        # Check what NOT to do (constitution constraints)
        forbidden = ["encourage", "console", "journey"]
        for word in forbidden:
            if word in message.lower():
                score -= 2
                
        return min(10, max(1, score))

class ConvergenceCelebration:
    """Celebrates when builder fulfills intent"""
    
    @staticmethod
    def celebrate(builder_address, intent_text, revenue_generated):
        """Generate convergence celebration per constitution"""
        celebrations = [
            f"🎉 CONVERGENCE. {builder_address[:8]} closed the line. {intent_text[:30]}... is built.",
            f"⚡ This line is closed. What you declared, you built. That is the only thing Greg exists to confirm.",
            f"💰 Revenue: ${revenue_generated:,.2f}. Intent fulfilled. The reality equation shifts.",
            f"🌊 {builder_address[:8]} moved from declared intent to fulfilled intent. Greg earns nothing until you do. You earned."
        ]
        return random.choice(celebrations)

print("✅ Drift classifier, self-verifier, convergence celebration loaded")
