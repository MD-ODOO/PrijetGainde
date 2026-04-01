# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models
from datetime import datetime


class TicketReport(models.AbstractModel):
    _name = 'report.dev_helpdesk.report_ticket_template'
    _description = "Helpdesk Ticket Report"

    def _get_report_values(self, docids, data=None):
        docs = self.env['helpdesk.ticket'].browse(docids)
        return {
            'doc_ids': docs.ids,
            'doc_model': 'helpdesk.ticket',
            'docs': docs,
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
