# -*- coding: utf-8 -*-

from odoo import fields, models


class Company(models.Model):
    _inherit = 'res.company'

    use_approval_route_customer_invoice = fields.Selection(
        string="Use Approval Route for Customer Invoices",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )
    use_approval_route_vendor_bill = fields.Selection(
        string="Use Approval Route for Vendor Bills",
        selection=[
            ('no', 'No'),
            ('optional', 'Optional'),
            ('required', 'Required')
        ],
        default='no',
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    use_approval_route_customer_invoice = fields.Selection(
        string="Use Approval Route for Customer Invoices",
        related='company_id.use_approval_route_customer_invoice',
        readonly=False,
    )
    use_approval_route_vendor_bill = fields.Selection(
        string="Use Approval Route for Vendor Bills",
        related='company_id.use_approval_route_vendor_bill',
        readonly=False,
    )
