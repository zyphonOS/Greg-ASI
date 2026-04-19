# Add to payment_verifier.py before if __name__ == '__main__'

from revenue_engine import revenue_engine

@app.route('/api/revenue-status', methods=['GET'])
def revenue_status():
    return jsonify(revenue_engine.get_status())

@app.route('/api/record-revenue', methods=['POST'])
def record_revenue():
    data = request.json
    amount = data.get('amount', 0)
    source = data.get('source', 'unknown')
    builder = data.get('builder', 'unknown')
    
    if amount <= 0:
        return jsonify({"error": "Amount must be positive"}), 400
    
    result = revenue_engine.record_revenue(amount, source, builder)
    return jsonify(result)

print("✅ Revenue endpoints added to backend")
