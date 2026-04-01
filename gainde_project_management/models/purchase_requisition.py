from odoo import models, fields


class PurchaseRequisition(models.Model):
    _inherit = 'purchase.requisition'

    project_id = fields.Many2one('project.project', string="Projet associé",
                                 index=True, ondelete='set null')
