from flask import Flask, request, jsonify
from flask import render_template
app = Flask(__name__)

@app.route('/intent_intent_547b2490', methods=['GET'])
def intent_547b2490_get():
    return render_template('intent_547b2490.html')

@app.route('/intent_intent_547b2490/waitlist', methods=['POST'])
def intent_547b2490_waitlist():
    # Add user to waitlist logic here
    return jsonify({'message': 'User added to waitlist'}), 201

if __name__ == '__main__':
    app.run(debug=True)