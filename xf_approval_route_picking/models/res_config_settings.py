# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route_picking = fields.Selection(
        string="Use Approval Route for Transfers",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route_picking = fields.Selection(
        string="Use Approval Route for Transfers",
        related='company_id.use_approval_route_picking',
        readonly=False,
    )
