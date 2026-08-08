# -*- coding: utf-8 -*-
"""Serveur de développement de la webapp : http.server sans cache.

Le http.server standard laisse le navigateur garder les fichiers en cache
(F5 sans effet après une modification). Ici : Cache-Control no-store.

Usage : python tools/serve_dev.py [port]   (défaut 8123)
"""

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent / "web" / "public"


class SansCache(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123
    handler = partial(SansCache, directory=str(RACINE))
    # 0.0.0.0 : accessible aussi depuis le téléphone sur le même wifi
    with ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"http://localhost:{port} (sans cache, racine {RACINE})")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
