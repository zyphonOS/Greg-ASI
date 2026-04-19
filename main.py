from flask import Blueprint, render_template

pingme_bp = Blueprint('pingme', __name__)

@pingme_bp.route('/pingme')
def pingme():
    return 'pong'

app.register_blueprint(pingme_bp)