# models/legal_litigation_stage.py
from odoo import models, fields


class LegalLitigationStage(models.Model):
    _name = 'legal.litigation.stage'
    _description = 'Étape Contentieux'
    _order = 'sequence, name'

    name = fields.Char(string="Nom de l'étape", required=True, translate=True,
                       store=True)
    sequence = fields.Integer(string="Séquence", default=10)
    fold = fields.Boolean(store=True,
                          string="Plié dans le Kanban",
                          help="Cette étape est pliée dans la vue Kanban par défaut."
                          )
