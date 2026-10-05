import os, sys
from waitress import serve

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()

print("--- Server on http://127.0.0.1:8000 ---")
serve(application, host="127.0.0.1", port=8000)
