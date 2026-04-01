# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models, api
from datetime import timedelta, date, datetime


class ticket_solution_document(models.Model):
    _name = 'ticket.solution.document'
    _description = 'Solution Document'


    document = fields.Binary(string="Document", required=True)
    description = fields.Text(string="Description")
    ticket_id = fields.Many2one("helpdesk.ticket",string="Helpdesk Ticket")

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
