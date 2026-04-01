# -*- coding: utf-8 -*-

from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.utils import ensure_db
from odoo.http import request
from odoo import http


class KsWeb(Home):
    def _web_client_readonly(self):
        return False

    @http.route('/clear/cache', type='json', auth="user")
    def clear_cache(self, **kwargs):
        request.env.registry.clear_cache()

    @http.route(['/web', '/odoo', '/odoo/<path:subpath>', '/scoped_app/<path:subpath>'], type='http', auth="none", readonly=_web_client_readonly)
    def web_client(self, s_action=None, **kw):
        ensure_db()
        user_id = request.env.user.browse(request.session.uid)
        if user_id.access_is_passwd_expired:
            request.session.logout()
        company_id = request.httprequest.cookies.get('cids') if request.httprequest.cookies.get('cids') else False
        if not kw.get('debug') or kw.get('debug') != "0":
            if company_id:
                lst = [int(x) for x in request.httprequest.cookies.get('cids').split('-')]
                profile_management = request.env['user.management'].sudo().search(
                    [('active', '=', True), ('access_disable_debug_mode', '=', True), ('access_company_ids', 'in', lst),
                     ('access_user_ids', 'in', user_id.id)], limit=1)
            else:
                profile_management = request.env['user.management'].sudo().search(
                    [('active', '=', True), ('access_disable_debug_mode', '=', True), ('access_user_ids', 'in', user_id.id)], limit=1)
            if profile_management:
                url = '/odoo'
                if kw.get('subpath'):
                    url = f"{url}/{kw.get('subpath')}"
                return request.redirect(f'{url}?debug=0')
        return super(KsWeb, self).web_client(s_action=s_action, **kw)
