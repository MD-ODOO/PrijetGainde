# -*- coding: utf-8 -*-
##############################################################################
#    
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Devintelle Solutions (<http://devintellecs.com/>).
#
##############################################################################

from odoo import api, fields, models, _

class ticket_tag_wizard(models.TransientModel):
    _name = "mass.ticket.tags"
    
    tags_ids = fields.Many2many('helpdesk.tag',string="Tags" , required=True)

    def update_tags(self):
        for data in self.env['helpdesk.ticket'].browse(self._context.get('active_ids')):
            data.tag_ids = [(6, 0, self.tags_ids.ids)]

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
