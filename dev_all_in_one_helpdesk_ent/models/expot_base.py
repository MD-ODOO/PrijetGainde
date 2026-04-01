# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################
import io
import base64
import xlsxwriter
from odoo import models, fields,api
import logging
_logger = logging.getLogger(__name__)
class ExportTemplate(models.Model):
    _name = 'export.template'
    _description = 'Export Template'

    name = fields.Char(string='Name')
    model_id = fields.Many2one('ir.model', string='Model')
    field_ids = fields.One2many('export.template.line','export_template_id', string='Fields')
    
   



class ExportTemplateLine(models.Model):
    _name = 'export.template.line'
    _description = 'Export Template Line'
 

    field_id = fields.Many2one('ir.model.fields',string="Field" , domain="[('model_id', '=', parent.model_id), ('ttype', 'not in', ['many2many', 'one2many'])]")
    field_label =fields.Char("Field Label")
    sequence=fields.Integer(string="Sequence")
    export_template_id=fields.Many2one('export.template',string="Export Template")
    
    
    @api.onchange('field_id')
    def onchange_field_label(self):
        self.field_label = self.field_id and self.field_id.field_description or ''










# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
