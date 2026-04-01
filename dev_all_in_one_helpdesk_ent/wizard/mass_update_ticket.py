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

class mass_update_ticket(models.TransientModel):
    _name = 'dev.mass.update.ticket'
    _description="Mass Update Tickets"
    
    update_user = fields.Boolean('Update Team/User')
    team_id = fields.Many2one('helpdesk.team', string='Team')
    assing_user_id = fields.Many2one('res.users', string='Assigned To')
    update_source = fields.Boolean('Update Source')
    source_id = fields.Many2one('utm.source', string='Source')
    
    update_priority = fields.Boolean('Update Priority')
    priority = fields.Selection([('0','Low'),
                                 ('1','Medium'), 
                                 ('2','High'), 
                                 ('3','Very High')], string='Priority', default='0')
    team_user_ids = fields.Many2many('res.users', string='team Users')

    @api.onchange('team_id')
    def onchange_team_id(self):
        for data in self:
            user_ids = self.env['res.users'].search([('share','=',False)]).ids
            data.team_user_ids = False
            if data.team_id:
                if data.team_id.privacy_visibility == 'invited_internal':
                    data.team_user_ids = data.team_id and data.team_id.member_ids and data.team_id.member_ids.ids
                else:
                    data.team_user_ids = user_ids
    
    def mass_update(self):
        active_ids = self._context.get('active_ids')
        ticket_ids = self.env['helpdesk.ticket'].browse(active_ids)
        vals={}
        if self.update_user:
            vals.update({
                'team_id':self.team_id and self.team_id.id or False,
                'user_id': self.assing_user_id and self.assing_user_id.id or False
            })
        if self.update_source:
            vals.update({
                'source_id':self.source_id and self.source_id.id or False,
            })
        if self.update_priority:
            vals.update({
                'priority':self.priority,
            })
        for ticket in ticket_ids:
            ticket.write(vals)
         
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
