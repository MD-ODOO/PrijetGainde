from odoo import http
from odoo.http import request

class ActionBlockController(http.Controller):

    def _is_action_enabled(self):
        # Exception: les administrateurs ne sont jamais bloqués.
        if request.env.user.has_group('base.group_system'):
            return True

        enabled = request.env['ir.config_parameter'].sudo().get_param(
            'action_toggle_control.enable_action_48'
        )
        return enabled == 'True'

    def _forbidden_response(self):
        return request.make_response(
            "Accès désactivé : cette action est bloquée par l'administrateur.",
            headers=[("Content-Type", "text/plain; charset=utf-8")],
            status=403,
        )

    @http.route('/odoo/action-540', auth='user')
    def block_odoo_action_540_prefixed(self, **kwargs):
        if not self._is_action_enabled():
            return self._forbidden_response()

        return request.redirect('/web#action=206')

    @http.route('/action-540', auth='user')
    def block_odoo_action_540(self, **kwargs):
        if not self._is_action_enabled():
            return self._forbidden_response()

        return request.redirect('/web#action=206')


    @http.route('/odoo/action-206', auth='user')
    def block_odoo_action_206_prefixed(self, **kwargs):
        if not self._is_action_enabled():
            return self._forbidden_response()

        return request.redirect('/web#action=206')

    @http.route('/action-206', auth='user')
    def block_odoo_action_206(self, **kwargs):
        if not self._is_action_enabled():
            return self._forbidden_response()

        return request.redirect('/web#action=206')

    @http.route('/odoo/action-48', auth='user')
    def block_odoo_action_48_prefixed(self, **kwargs):
        if not self._is_action_enabled():
            return self._forbidden_response()

        return request.redirect('/web#action=48')


    @http.route('/action-48', auth='user')
    def block_action(self, **kwargs):
        if not self._is_action_enabled():
            return self._forbidden_response()

        return request.redirect('/web#action=48')
