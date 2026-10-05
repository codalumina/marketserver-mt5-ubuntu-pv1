import logging
import os
import sys
from waitress import serve

# Configure standard logging format
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

from django.core.wsgi import get_wsgi_application

django_app = get_wsgi_application()


# Lightweight WSGI Middleware to intercept and log requests/responses
class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        method = environ.get("REQUEST_METHOD")
        path = environ.get("PATH_INFO")
        query = environ.get("QUERY_STRING", "")
        full_path = f"{path}?{query}" if query else path

        status_captured = ["200 OK"]

        def modified_start_response(status, response_headers, exc_info=None):
            status_captured[0] = status
            return start_response(status, response_headers, exc_info)

        # Execute request through Django
        response = self.app(environ, modified_start_response)

        # Print clean access log line
        logging.info(f"{method} {full_path} -> Status: {status_captured[0]}")
        return response


# Wrap Django app with the logger middleware
application = RequestLoggingMiddleware(django_app)

print("--- Server running on http://127.0.0.1:8000 ---")
serve(application, host="127.0.0.1", port=8000, ident="waitress")
