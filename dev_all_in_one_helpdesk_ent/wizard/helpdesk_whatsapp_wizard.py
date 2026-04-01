# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class helpdesk_whatsapp_wizard(models.TransientModel):
    _name = "helpdesk.whatsapp.wizard"

    whatsapp_template_id = fields.Many2one("whatsapp.message.template", string="Template")
    partner_id = fields.Many2one("res.partner", string="Customer")
    mobile = fields.Char(string="Mobile")
    
    whatsapp_message = fields.Html(string='Message')    
    
    @api.onchange('whatsapp_template_id')
    def onchange_whatsapp_template(self):
        for data in self:
            data.whatsapp_message = data.whatsapp_template_id and data.whatsapp_template_id.whatsapp_message or ' '
            
    def send_wha_message(self):
        active_id = self.env['helpdesk.ticket'].browse(self._context.get('active_id'))
        partner_name = active_id.partner_id and active_id.partner_id.name or ' '
        ticket_sequnce = active_id.ticket_sequnce or ' '
        if not active_id.partner_phone:
            raise ValidationError(_('''Please specify Phone number for : %s''') % (active_id.partner_id.name or ' '))
        else:
            url = 'https://web.whatsapp.com/send?phone='
            message = 'Hello%20*' + partner_name.replace(' ', '*%20*') + '%0a'
            message += 'Your Ticket Number :' + ticket_sequnce + ',*%0a'
            message_template = str(self.whatsapp_message).replace('<p>', ' ')
            message_tem_final = message_template.replace('<br>', ' ')
            message += message_tem_final.replace('</p>', '%0a')
            url += str(self.mobile) + "&text=" + str(message)
            return {'type': 'ir.actions.act_url', 'name': "Sending Message", 'target': 'new', 'url': url}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
