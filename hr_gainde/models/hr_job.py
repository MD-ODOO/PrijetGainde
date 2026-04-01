# -*- coding: utf-8 -*-

from odoo import models, fields, api, _




class CercoFunction(models.Model):
    _name = 'cerco.function'
    _description = 'Fonction personnalisée'

    name = fields.Char(string='Fonction', required=True)
    job_id = fields.Many2one('hr.job', string='Poste', required=True)
    code = fields.Integer(string='Code')

    _sql_constraints = [
        ('code_uniq', 'unique (code)', 'Le code doit être unique !')
    ]
