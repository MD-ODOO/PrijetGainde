# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api


class HelpdeskTicketType(models.Model):
    _name = 'helpdesk.ticket.type'
    _description = 'Type de Ticket Helpdesk'
    _order = 'sequence, id'
    _rec_name = 'reclamations'

    sequence = fields.Integer(string='Séquence', default=10)
    reclamations = fields.Char(string='Réclamations', required=True)
    type_reclamation = fields.Char(string='Type de réclamation', required=True)
    active = fields.Boolean(string='Actif', default=True)

    _sql_constraints = [
        ('reclamations_unique', 'unique(reclamations)', 'La réclamation doit être unique!')
    ]


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

