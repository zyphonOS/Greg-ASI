# Add to payment_verifier.py - Builder onboarding endpoint

@app.route('/api/onboard-builder', methods=['POST'])
def onboard_builder():
    data = request.json
    builder_address = data.get('builder_address')
    email = data.get('email')
    
    if not builder_address:
        return jsonify({"error": "Missing builder_address"}), 400
    
    # Store builder in soul file
    soul_file = Path("data/greg_soul/builders.json")
    soul_file.parent.mkdir(parents=True, exist_ok=True)
    
    if soul_file.exists():
        with open(soul_file, 'r') as f:
            builders = json.load(f)
    else:
        builders = {}
    
    builders[builder_address] = {
        "email": email,
        "onboarded_at": datetime.utcnow().isoformat(),
        "intent_count": 0,
        "revenue_contributed": 0.0
    }
    
    with open(soul_file, 'w') as f:
        json.dump(builders, f, indent=2)
    
    return jsonify({
        "status": "onboarded",
        "builder": builder_address,
        "message": "Welcome to Greg. Declare your intent."
    })

print("✅ Builder onboarding endpoint added")
