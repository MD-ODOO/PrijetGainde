# -*- coding: utf-8 -*-
from odoo import models, fields, api


class AuditGaindeControl(models.Model):
    _name = 'audit_gainde.control'
    _description = 'Contrôle Audit Gainde'
    _rec_name = 'description'

    description = fields.Text(
        string='Description du contrôle',
        required=True,
        help="Ex: 'Signature DG', 'Contrôle croisé'"
    )

    control_type = fields.Selection([
        ('preventive', 'Préventif'),
        ('detective', 'Détectif'),
        ('corrective', 'Correctif')
    ], string='Type', default='preventive', required=True)

    frequency = fields.Selection([
        ('transaction', 'À chaque transaction'),
        ('daily', 'Quotidien'),
        ('weekly', 'Hebdo'),
        ('monthly', 'Mensuel'),
        ('annual', 'Annuel'),
        ('ad_hoc', 'À la demande')
    ], string='Fréquence', default='monthly', required=True)



    efficacy = fields.Selection([
        ('high', 'Efficace'),
        ('medium', 'Partiel'),
        ('low', 'Faible'),
        ('none', 'Aucun')
    ], string='Efficacité', default='medium')

    # Relations
    risk_id = fields.Many2one(
        'audit_gainde.risk',
        string='Risques couverts'
    )

