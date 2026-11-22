import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DATA_FILE = "feed_data.json"
CREATOR_PIN = "2026"  # Tum apna pin yahan badal sakte ho


class HubHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/api/delete":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body.decode("utf-8"))
            except Exception:
                self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                return

            if str(payload.get("pin", "")) != CREATOR_PIN:
                self._send_json(403, {"ok": False, "error": "Wrong Creator PIN"})
                return

            item_id = payload.get("id")
            category = payload.get("category")  # "shorts", "videos", or "photos"

            if not os.path.exists(DATA_FILE):
                self._send_json(404, {"ok": False, "error": "feed_data.json not found"})
                return

            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            removed = False
            categories_to_check = [category] if category in ("shorts", "videos", "photos") else ("shorts", "videos", "photos")
            for cat in categories_to_check:
                before = len(data.get(cat, []))
                data[cat] = [x for x in data.get(cat, []) if x.get("id") != item_id]
                if len(data[cat]) < before:
                    removed = True

            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self._send_json(200, {"ok": True, "removed": removed})
        else:
            self.send_error(404)

    def _send_json(self, code, obj):
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = ThreadingHTTPServer(("0.0.0.0", 8080), HubHandler)
    print("ZAIN VIRAL HUB running at http://localhost:8080")
    server.serve_forever()
