# -*- coding: utf-8 -*-
######################################################################
#                                                                    #
# Part of EKIKA CORPORATION PRIVATE LIMITED (Website: ekika.co).     #
# See LICENSE file for full copyright and licensing details.         #
#                                                                    #
######################################################################

from werkzeug.exceptions import NotFound
from odoo import models
from odoo import http
from odoo.http import request
from odoo.fields import Datetime

OLD_SESSION_LIFETIME = http.SESSION_LIFETIME

session_cache = {
    # 'sid': [rec_id, last_act, ip_add]
}

def get_session_detail(sid):
    rec = request.env['user.session.detail'].sudo().search(
                [('session_identifier', '=', sid)], order='id desc', limit=1)
    if rec:
        return rec
    else:
        now_time = Datetime.now()
        return request.env['user.session.detail'].sudo().create({
            'user_id': request.session.uid,
            'session_identifier': request.session.sid,
            'first_activity': now_time,
            'last_activity': now_time,
            'ip_address': request.httprequest.remote_addr,
            'device_platform': request.httprequest.user_agent.platform,
            'browser': request.httprequest.user_agent.browser,
        })


class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _authenticate(cls, endpoint):
        super()._authenticate(endpoint)
        cls._update_user_session_details()

    @classmethod
    def _pre_dispatch(cls, rule, args):
        super()._pre_dispatch(rule, args)
        cls._update_user_session_expiry()

    @classmethod
    def _update_user_session_expiry(cls):
        if request.env['ir.config_parameter'].sudo().get_param('user_session_manage.session_expiry_management'):
            session_expiry_conf = request.env['ir.config_parameter'].sudo().get_param(
                'user_session_manage.session_expiry_configuration')
            if session_expiry_conf == '1_day':
                http.SESSION_LIFETIME = 86400
            elif session_expiry_conf == '2_days':
                http.SESSION_LIFETIME = 172800
            elif session_expiry_conf == '4_days':
                http.SESSION_LIFETIME = 345600
            elif session_expiry_conf == '7_days':
                http.SESSION_LIFETIME = 604800
            elif session_expiry_conf == '14_days':
                http.SESSION_LIFETIME = 1209600
            elif session_expiry_conf == 'user_based':
                cls._manage_session_expiry_user_based()
        else:
            http.SESSION_LIFETIME = OLD_SESSION_LIFETIME

    @classmethod
    def _manage_session_expiry_user_based(cls):
        if request.env.user:
            http.SESSION_LIFETIME = int(request.env.user.session_expiry_hours * 3600)

    @classmethod
    def _update_user_session_details(cls):
        cur_sid = request.session.sid
        if not all([request.session.uid, request.session.session_token, cur_sid]):
            return

        session_id, last_activity, ip_address = session_cache.get(cur_sid, [None, None, None])
        
        if not session_id:
            # Create or get session
            user_session = get_session_detail(cur_sid)
            session_id = user_session.id
            last_activity = Datetime.to_datetime(user_session.last_activity)
            ip_address = user_session.ip_address
            session_cache[cur_sid] = [session_id, last_activity, ip_address]

        values = {}
        if (Datetime.now() - last_activity).seconds > 60:
            values['last_activity'] = Datetime.now()
        if (request.httprequest.remote_addr != ip_address):
            values['ip_address'] = request.httprequest.remote_addr

        # Save if required
        if values:
            session_rec = request.env['user.session.detail'].sudo().browse(session_id)
            if 'ip_address' in values:
                values['connected_ip_addresses'] = f'{session_rec.connected_ip_addresses}\n{values["ip_address"]}'
            session_rec.write(values)
            last_activity = values.get('last_activity') or Datetime.now()
            session_cache[cur_sid] = [session_id, last_activity, request.httprequest.remote_addr]

    @classmethod
    def _post_logout(cls):
        super()._post_logout()
        session_rec = request.env['user.session.detail'].sudo().search(
            [('session_identifier', '=', request.session.sid)], order='id desc', limit=1)
        if session_rec:
            session_cache.pop(session_rec.session_identifier, False)
            session_rec.unlink()
