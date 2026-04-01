from odoo import http
from odoo.http import request

class URLFirewall(http.Controller):

    BLOCKED_URLS = [
        '/users',
        '/web/settings',
        '/web/database/manager',
        '/web#action',
        '/web#menu_id',
        '/odoo/users',
        '/odoo/web/settings',
        '/odoo/web/database/manager',
        '/odoo/web#action',
        '/odoo/web#menu_id',
    ]

    @http.route('/<path:path>', auth='user', csrf=False)
    def firewall(self, path=None, **kwargs):
        enabled = request.env['ir.config_parameter'].sudo().get_param(
            'url_firewall.enable_url_firewall'
        )

        def plain_not_found():
            return request.make_response(
                "404 Not Found",
                headers=[("Content-Type", "text/plain; charset=utf-8")],
                status=404,
            )

        if enabled != 'True':
            return plain_not_found()

        full_path = '/' + (path or '')
        user = request.env.user

        # 1. Administrateurs → accès autorisé
        if user.has_group('base.group_system'):
            return plain_not_found()

        # 2. Utilisateurs autorisés → accès autorisé
        if user.has_group('url_firewall.group_url_bypass'):
            return plain_not_found()

        # 3. Firewall → blocage
        for blocked in self.BLOCKED_URLS:
            if full_path.startswith(blocked):
                return request.make_response(
                    "Accès interdit : cette URL est protégée par le firewall.",
                    headers=[("Content-Type", "text/plain; charset=utf-8")],
                    status=403,
                )

        return plain_not_found()
