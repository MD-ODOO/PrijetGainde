# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route_customer_payment = fields.Selection(
        string="Use Approval Route for Customer Payments",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )
    use_approval_route_supplier_payment = fields.Selection(
        string="Use Approval Route for Supplier Payments",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route_customer_payment = fields.Selection(
        string="Use Approval Route for Customer Payments",
        related='company_id.use_approval_route_customer_payment',
        readonly=False,
    )

    use_approval_route_supplier_payment = fields.Selection(
        string="Use Approval Route for Supplier Payments",
        related='company_id.use_approval_route_supplier_payment',
        readonly=False,
    )
