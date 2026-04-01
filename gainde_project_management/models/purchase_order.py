from odoo import models, api, fields, _
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one('project.project', string="Projet associé")

    @api.constrains('project_id', 'state')
    def _check_purchase_from_project(self):
        """verification si il y'a demande d'achat lié au projet"""
        for order in self:
            if order.project_id and order.state in ('purchase', 'done'):

                requisition = self.env['purchase.requisition'].search([
                    ('project_id', '=', order.project_id.id),
                    ('state', 'in', ('done', 'in_progress'))
                ], limit=1)
                if not requisition:
                    raise ValidationError(
                        _("Impossible de créer une commande d'achat directe pour ce projet. "
                          "Passez d’abord par une demande d’achat (RFQ).")
                    )

    def action_assign_project_wizard(self):
        """Cette méthode ouvre le wizard depuis le bouton du header"""
        return {
            'name': 'Assigner Projet aux Lignes',
            'type': 'ir.actions.act_window',
            'res_model': 'assign.project.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_id': self.id},
        }
