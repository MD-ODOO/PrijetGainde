# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)

# =====================
# Bien transport
# =====================
class HrTicketTransport(models.Model):
    _name = 'hr.ticket.transport'
    _description = 'Bien transport'

    name = fields.Char(string='Bien transport', required=True)
    year_id = fields.Many2one('res.year', string='Année', required=True)
    amount = fields.Float(string='Montant')
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id
    )
    delivrate = fields.Boolean(string='Délivré(s) ?')
    employee_id = fields.Many2one('hr.employee', string='Employé')


# =====================
# Billets
# =====================
class HrTicket(models.Model):
    _name = 'hr.ticket'
    _description = 'Billet employé'

    name = fields.Char(string='Billet', required=True)
    year_id = fields.Many2one('res.year', string='Année', required=True)
    amount = fields.Float(string='Montant')
    currency_id = fields.Many2one(
        'res.currency',
        string='Devise',
        readonly=True,
        default=lambda self: self.env.user.company_id.currency_id
    )
    number = fields.Integer(string='Nombre')
    delivrate = fields.Boolean(string='Billet(s) délivré(s) ?')
    employee_id = fields.Many2one('hr.employee', string='Employé')


# =====================
# Année
# =====================
class ResYear(models.Model):
    _name = 'res.year'
    _description = 'Année de référence'

    name = fields.Char(string="Année", required=True)
