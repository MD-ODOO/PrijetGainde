# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#s
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models,api,_
from odoo.exceptions import ValidationError

class crm_lead(models.Model):
    _inherit = 'crm.lead'
    
    ticket_count = fields.Integer(string='Ticket Orders', compute='_compute_ticket_count')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket')
    
    
#    @api.depends('picking_ids')
    def _compute_ticket_count(self):
        for order in self:
            ticket_ids = self.env['helpdesk.ticket'].search([('lead_id','=',self.id)])
            order.ticket_count = len(ticket_ids)
    
    @api.model
    def create(self,vals):
        lead_id = super(crm_lead,self).create(vals)
        if lead_id.ticket_id:
            attachment_ids = self.env['ir.attachment'].search([('res_id','=',lead_id.ticket_id.id),
                                                               ('res_model','=','helpdesk.ticket')])
            if attachment_ids:
                for att in attachment_ids:
                    att.copy({'res_model': 'crm.lead','res_id':lead_id.id})
        return lead_id
    
    def create_ticket(self):
        for data in self:
            return {
                'name': _('Ticket'),
                'view_mode': 'form',
                'res_model': 'helpdesk.ticket',
                'view_id': self.env.ref('helpdesk.helpdesk_ticket_view_form').id,
                'type': 'ir.actions.act_window',
                'context': {'default_name': self.name,
                            'default_partner_id': self.partner_id and self.partner_id.id or False,
                            'default_email': self.email_from,
                            'default_lead_ticket_flag': True,
                            'default_lead_id': self.id,
                            },
                'target': 'new'
            }
            
            
            
            
            
            
            
            
    def action_view_ticket(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_my').read()[0]
        ticket_ids = self.env['helpdesk.ticket'].search([('lead_id','=',self.id)])
        if len(ticket_ids) > 1:
            action['domain'] = [('id', 'in', ticket_ids.ids)]
        elif ticket_ids:
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
            action['res_id'] = ticket_ids.id
        return action
            
#            return self.env.ref('dev_helpdesk.form_ticket_view')
#    
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
