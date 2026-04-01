# -*- coding: utf-8 -*-
######################################################################
#                                                                    #
# Part of EKIKA CORPORATION PRIVATE LIMITED (Website: ekika.co).     #
# See LICENSE file for full copyright and licensing details.         #
#                                                                    #
######################################################################

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    session_limit_management = fields.Boolean(string='Enable Session Limit Management', default=False,
        config_parameter='user_session_manage.session_limit_management')
    session_limit_configuration = fields.Selection(selection=[
        ('one_session_all_user', 'One Session for all Users'), ('user_based', 'Based On User Configuration')],
        default='one_session_all_user', config_parameter='user_session_manage.session_limit_configuration')

    session_expiry_management = fields.Boolean(string='Enable Session Expiry Management', default=False,
        config_parameter='user_session_manage.session_expiry_management')
    session_expiry_configuration = fields.Selection(selection=[
        ('4_hours', '4 Hours'), ('8_hours', '8 Hours'),
        ('1_day', '1 Day'), ('2_days', '2 Days'), ('4_days', '4 Days'), ('7_days', '7 Days'), ('14_days', '14 Days'),
        ('user_based', 'Based On User Configuration')],
        default='4_hours', config_parameter='user_session_manage.session_expiry_configuration')
