# ===== OSI QUERY LAYER ENDPOINTS =====
import asyncio
from osi_query import query_intent

@app.route('/api/osi-query', methods=['POST'])
def osi_query():
    """Query OSI for intent-relevant live data"""
    data = request.json
    intent_text = data.get('intent_text')
    builder_address = data.get('builder_address')
    
    if not intent_text:
        return jsonify({"error": "Missing intent_text"}), 400
    
    # Run async query in event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(query_intent(intent_text))
    loop.close()
    
    return jsonify(result)

@app.route('/api/osi-stream', methods=['GET'])
def osi_stream():
    """Stream OSI insights (SSE for real-time updates)"""
    def generate():
        # This would be a real SSE stream in production
        yield f"data: OSI layer active\n\n"
    
    return Response(generate(), mimetype='text/event-stream')

print("✅ OSI endpoints added to backend")
