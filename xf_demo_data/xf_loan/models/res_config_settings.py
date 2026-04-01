# -*- coding: utf-8 -*-

from odoo import fields, models


class CompanyLoanSettings(models.AbstractModel):
    _name = 'res.company.loan.settings'
    _description = 'Loan Module Settings Abstract'

    max_num_months = fields.Integer(
        string="Max. Number of Months",
        default=0,
    )
    max_loan_amount = fields.Float(
        string='Max. Loan Amount',
        default=0,
    )


class Company(models.Model):
    _name = 'res.company'
    _inherit = ['res.company', 'res.company.loan.settings']

    max_loan_amount = fields.Monetary()


class ResConfigSettings(models.TransientModel):
    _name = 'res.config.settings'
    _inherit = ['res.config.settings', 'res.company.loan.settings']

    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string="Company Currency", readonly=True)
    max_num_months = fields.Integer(
        related='company_id.max_num_months',
        readonly=False,
    )
    max_loan_amount = fields.Monetary(
        related='company_id.max_loan_amount',
        currency_field='company_currency_id',
        readonly=False,
    )
