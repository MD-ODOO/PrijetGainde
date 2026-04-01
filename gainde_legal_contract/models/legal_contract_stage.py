from odoo import models, fields, api


class LegalContractStage(models.Model):
    _name = 'legal.contract.stage'
    _description = 'Étape Contrat'
    _order = 'sequence'

    name = fields.Char(required=True, store=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean("Plié dans Kanban", store=True)
