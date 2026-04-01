#-*- coding:utf-8 -*-

from odoo import models, fields, api, _


class CercoConvention(models.Model):
    _name = "cerco.convention"
    _description = "Convention collective"

    name = fields.Char(string='Nom convention', required=True)
    line_ids = fields.One2many(
        'line.cerco.convention',
        'conv_id',
        string='Lignes de convention'
    )


class LineCercoConvention(models.Model):
    _name = "line.cerco.convention"
    _description = "Ligne de convention collective"

    name = fields.Char(string='Libellé', required=True)
    code = fields.Char(string='Code Grille')
    taux_h = fields.Float(string='Taux horaire',default=173.33)
    wage = fields.Float(string='Salaire de base')
    conv_id = fields.Many2one(
        'cerco.convention',
        string="Convention Collective ",
        ondelete='cascade',default='Commerce'
        
    )



