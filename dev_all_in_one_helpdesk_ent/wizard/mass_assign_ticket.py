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

class mass_ticket_assign(models.TransientModel):
    _name = 'dev.mass.ticket.assign'
    _description="Mass Update Team"
    
    team_id = fields.Many2one('helpdesk.team', string='Team')
    team_user_ids = fields.Many2many('res.users','team_user_ids',string='team Users')
    assing_user_id = fields.Many2one('res.users', string='Assigned To')
    multi_user_ids = fields.Many2many('res.users', string='Assign Multi Users')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self:self.env.company)
    allow_multi_user = fields.Boolean('Multi Users', compute='_set_allow_multi_user')
    
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
    
    @api.depends('company_id')
    def _set_allow_multi_user(self):
        for rec in self:
            rec.allow_multi_user = False
            if rec.company_id.allow_multi_user:
                rec.allow_multi_user = True
    
    def action_update_team(self):
         active_ids = self._context.get('active_ids')
         ticket_ids = self.env['helpdesk.ticket'].browse(active_ids)
         for ticket in ticket_ids:
            if ticket.team_id.id == self.team_id.id:
                vals ={
                    'team_id':self.team_id and self.team_id.id or False,
                    'user_id':self.assing_user_id and self.assing_user_id.id or False,
                }
                if self.assing_user_id:
                    vals.update({
                        'user_id':self.assing_user_id and self.assing_user_id.id or False,
                    })
                if self.multi_user_ids:
                    vals.update({
                        'multi_user_ids':[(6,0, self.multi_user_ids.ids)]
                    })
                ticket.write(vals)
            else:
                vals={
                    'team_id':self.team_id and self.team_id.id or False,
                    'user_id':self.assing_user_id and self.assing_user_id.id or False,
#                    'assing_user_id':self.assing_user_id and self.assing_user_id.id or False,
                }
                if self.multi_user_ids:
                    vals.update({
                        'multi_user_ids':[(6,0, self.multi_user_ids.ids)]
                    })
                else:
                    vals.update({
                        'multi_user_ids':[(6,0, [])]
                    })
                ticket.write(vals)
         
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
