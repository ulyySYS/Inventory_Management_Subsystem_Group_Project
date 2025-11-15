import sys
from pathlib import Path

# Ensure project root is on sys.path so we can import flask_site when running from tools/
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from flask_site import app
from jinja2 import TemplateSyntaxError

with app.app_context():
    try:
        t = app.jinja_env.get_template('home.html')
        print('Template compiled OK')
    except TemplateSyntaxError as e:
        import traceback
        traceback.print_exc()
        # jinja2 TemplateSyntaxError exposes lineno and message attributes
        lineno = getattr(e, 'lineno', None)
        message = getattr(e, 'message', str(e))
        print('\nTemplateSyntaxError at line:', lineno)
        print('Message:', message)
