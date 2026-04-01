# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models,api,_
from odoo.exceptions import ValidationError

class dev_knowledge(models.Model):
    _name = 'dev.knowledge'
    _description = 'Knowledge'
    
    name = fields.Char('Question')
    solution = fields.Html('Solution')
    category_id = fields.Many2one('dev.knowledge.category', string='Category')
    tag_ids = fields.Many2many('dev.knowledge.tags', string='Tags')
    active = fields.Boolean('Active', default=True)
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
