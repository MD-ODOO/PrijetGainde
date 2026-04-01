from odoo import http
from odoo.http import request, Response
import json


class AssetInventoryScanController(http.Controller):

    @http.route("/asset-inventory/scan", auth="user", website=False, type="http")
    def scan_page(self, session_id=None, **kwargs):
        """Page PWA dédiée au scan mobile d'inventaire."""
        user = request.env.user
        sessions = request.env["asset.inventory"].search(
            [("state", "=", "in_progress")], order="date_start desc"
        )
        selected = None
        if session_id:
            selected = request.env["asset.inventory"].browse(int(session_id))
            if not selected.exists() or selected.state != "in_progress":
                selected = None
        if not selected and sessions:
            selected = sessions[0]

        sessions_data = [
            {"id": s.id, "name": s.name, "date": str(s.date_start)}
            for s in sessions
        ]
        selected_data = (
            {
                "id": selected.id,
                "name": selected.name,
                "date": str(selected.date_start),
                "scanned": selected.scanned_count,
                "missing": selected.missing_count,
            }
            if selected
            else None
        )

        return request.render(
            "asset_management_override.asset_inventory_scan_page",
            {
                "sessions_json": json.dumps(sessions_data),
                "selected_json": json.dumps(selected_data),
                "user_name": user.name,
                "csrf_token": request.csrf_token(),
            },
        )

    @http.route("/asset-inventory/scan/manifest.json", auth="public", type="http")
    def pwa_manifest(self, **kwargs):
        manifest = {
            "name": "Inventaire Actifs",
            "short_name": "Asset Scan",
            "description": "Scanner les codes-barres des actifs pour l'inventaire",
            "start_url": "/asset-inventory/scan",
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#ffffff",
            "theme_color": "#875A7B",
            "icons": [
                {
                    "src": "/asset_management_override/static/src/pwa/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
                {
                    "src": "/asset_management_override/static/src/pwa/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any maskable",
                },
            ],
            "categories": ["business", "utilities"],
        }
        return Response(
            json.dumps(manifest),
            content_type="application/manifest+json",
            headers={"Cache-Control": "no-cache"},
        )

    @http.route("/asset-inventory/scan/sw.js", auth="public", type="http")
    def service_worker(self, **kwargs):
        """Service worker minimal pour permettre l'installation PWA."""
        sw_js = """
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', () => self.clients.claim());
self.addEventListener('fetch', (event) => {
    // Réseau en priorité — pas de cache offline (données live Odoo)
    event.respondWith(fetch(event.request).catch(() => new Response('Offline', {status: 503})));
});
"""
        return Response(
            sw_js,
            content_type="application/javascript",
            headers={"Service-Worker-Allowed": "/asset-inventory/"},
        )
