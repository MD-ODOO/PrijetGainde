# -*- coding: utf-8 -*-
######################################################################
#                                                                    #
# Part of EKIKA CORPORATION PRIVATE LIMITED (Website: ekika.co).     #
# See LICENSE file for full copyright and licensing details.         #
#                                                                    #
######################################################################

from odoo import models, fields


class UserLoginHistory(models.Model):
    _name = 'user.login.history'
    _description = 'User Login History'

    user_id = fields.Many2one('res.users', required=True)
    login_datetime = fields.Datetime('Login Time')

