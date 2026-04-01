from odoo import models, fields


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.request'

    project_id = fields.Many2one('project.project', string="Projet associé",
                                 index=True, ondelete='set null')
