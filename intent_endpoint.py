# Add this to payment_verifier.py (before the if __name__ block)

@app.route('/api/declare-intent', methods=['POST'])
def declare_intent():
    from intent_storage import intent_storage
    
    data = request.json
    builder_address = data.get('builder_address')
    intent_text = data.get('intent_text')
    
    if not builder_address or not intent_text:
        return jsonify({"error": "Missing builder_address or intent_text"}), 400
    
    # Verify access
    if builder_address.lower() != ADMIN_WALLET.lower() and builder_address.lower() not in verified_builders:
        return jsonify({"error": "Access denied"}), 403
    
    # Save intent
    intent_record = intent_storage.save_intent(builder_address, intent_text)
    
    # Calculate initial reality equation contribution
    reality_impact = {
        "epsilon_improvement": 0.01,  # Each intent improves ε slightly
        "message": f"Intent declared. Greg will measure drift every tick."
    }
    
    return jsonify({
        "status": "intent_recorded",
        "intent": intent_record,
        "reality_impact": reality_impact
    })

print("✅ Intent declaration endpoint added")
