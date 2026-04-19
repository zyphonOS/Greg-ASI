@app.route('/api/drift-visualization', methods=['GET'])
def drift_visualization():
    """Return drift data for visualization"""
    builder_address = request.args.get('builder_address')
    if not builder_address:
        return jsonify({"error": "Missing builder_address"}), 400
    
    # Get drift history from tick log
    tick_log = Path("data/greg_soul/tick_log.json")
    if tick_log.exists():
        with open(tick_log, 'r') as f:
            ticks = json.load(f)
        
        # Extract drift scores for this builder (simplified - would filter by builder in production)
        drift_history = [t.get('drift_score', 0) for t in ticks[-50:]]
        
        return jsonify({
            "drift_history": drift_history,
            "current_drift": drift_history[-1] if drift_history else 0,
            "trend": "increasing" if len(drift_history) > 1 and drift_history[-1] > drift_history[-2] else "decreasing"
        })
    return jsonify({"drift_history": [], "current_drift": 0, "trend": "stable"})
