"""
Simple HTTP server for health checks and monitoring.
"""
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

from mc_backup.utils.health import HealthChecker


class HealthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for health checks."""
    
    def __init__(self, health_checker: HealthChecker, *args, **kwargs):
        self.health_checker = health_checker
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/health':
            self._handle_health_check()
        elif self.path == '/status':
            self._handle_status()
        else:
            self._send_response(404, {"error": "Not found"})
    
    def _handle_health_check(self):
        """Handle detailed health check."""
        health_data = self.health_checker.check_health()
        status_code = 200 if health_data["status"] == "healthy" else 503
        self._send_response(status_code, health_data)
    
    def _handle_status(self):
        """Handle simple status check."""
        summary = self.health_checker.get_health_summary()
        self._send_response(200, {"status": summary})
    
    def _send_response(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response."""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = json.dumps(data, indent=2)
        self.wfile.write(response.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


class HealthServer:
    """Simple HTTP server for health monitoring."""
    
    def __init__(self, port: int = 8080, health_checker: HealthChecker = None):
        self.port = port
        self.health_checker = health_checker or HealthChecker(None)
        self.server = None
        self.server_thread = None
        self.running = False
    
    def start(self):
        """Start the health server in a separate thread."""
        if self.running:
            return
        
        try:
            # Create handler with health checker
            def handler(*args, **kwargs):
                return HealthHandler(self.health_checker, *args, **kwargs)
            
            self.server = HTTPServer(('0.0.0.0', self.port), handler)
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            self.running = True
            
        except Exception as e:
            if self.health_checker.log:
                self.health_checker.log.error(f"Failed to start health server: {e}")
    
    def _run_server(self):
        """Run the HTTP server."""
        try:
            self.server.serve_forever()
        except Exception as e:
            if self.health_checker.log:
                self.health_checker.log.error(f"Health server error: {e}")
    
    def stop(self):
        """Stop the health server."""
        if self.server and self.running:
            self.server.shutdown()
            self.server.server_close()
            self.running = False
