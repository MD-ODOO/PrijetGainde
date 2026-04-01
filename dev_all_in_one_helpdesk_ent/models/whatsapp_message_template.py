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

class whatsapp_message_template(models.Model):
    _name = "whatsapp.message.template"
    
    
    name = fields.Char('Name', required="1")
    whatsapp_message = fields.Html(string='Message')        

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
