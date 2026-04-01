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

class knowledge_tags(models.Model):
    _name = 'dev.knowledge.tags'
    _description = 'Knowledge Tags'
    
    name = fields.Char('Name')
    color = fields.Integer()
    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
