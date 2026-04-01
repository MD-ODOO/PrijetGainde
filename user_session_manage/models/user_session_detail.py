# -*- coding: utf-8 -*-
######################################################################
#                                                                    #
# Part of EKIKA CORPORATION PRIVATE LIMITED (Website: ekika.co).     #
# See LICENSE file for full copyright and licensing details.         #
#                                                                    #
######################################################################

import os
import odoo
from odoo.http import request
from odoo import models, fields, api
from odoo.addons.base.models.res_users import check_identity
from odoo.addons.user_session_manage.models.ir_http import session_cache


class UserSessionDetails(models.Model):
    _name = 'user.session.detail'
    _description = 'User Session Detail'

    user_id = fields.Many2one('res.users', required=True)
    session_identifier = fields.Char('Session Identifier', required=True)
    ip_address = fields.Char('IP Address', required=True)
    device_platform = fields.Char('Device Platform')
    browser = fields.Char('Browser')
    first_activity = fields.Char('First Activity')
    last_activity = fields.Char('Last Activity')
    is_current_login = fields.Boolean('Is Current Login', compute='_compute_is_current_login')
    connected_ip_addresses = fields.Text('Connected Ip Addresses')
    is_last_login_display = fields.Boolean('Last Login Displayed')

    def _compute_is_current_login(self):
        for rec in self:
            rec.is_current_login = rec.session_identifier == request.session.sid

    @check_identity
    def logout(self):
        self.ensure_one()
        return self._logout()

    def _logout(self):
        path = odoo.tools.config.session_dir
        session_path = f'{path}/{self.session_identifier[:2]}/{self.session_identifier}'
        if os.path.exists(session_path):
            os.remove(session_path)
        is_current_device = self.is_current_login
        self.unlink()
        if is_current_device:
            request.session.logout(keep_db=True)

    @api.model
    def get_current_session_of_user(self):
        records = self.search([('user_id', '=', request.env.user.id)])
        for rec in records:
            if rec.is_current_login:
                return rec.session_identifier

    def mark_last_login_display(self):
        self.sudo().write({'is_last_login_display': True})

    def _cron_remove_absent_session_records(self):
        session_recs = self.env['user.session.detail'].search([])
        path = odoo.tools.config.session_dir
        for rec in session_recs:
            session_path = f'{path}/{rec.session_identifier[:2]}/{rec.session_identifier}'
            if not os.path.exists(session_path):
                session_cache.pop(rec.session_identifier, False)
                rec.unlink()
