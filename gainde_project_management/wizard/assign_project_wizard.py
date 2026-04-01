from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AssignProjectWizard(models.TransientModel):
    _name = 'assign.project.wizard'
    _description = 'Wizard pour Assignation de Projet aux Lignes d\'Achat'

    project_id = fields.Many2one('project.project', string="Projet à Assigner",
                                 required=True)
    purchase_line_ids = fields.Many2many('purchase.order.line',
                                         string="Lignes Sélectionnées")

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_ids = self.env.context.get('active_ids')
        if active_ids:
            purchase = self.env['purchase.order'].browse(active_ids[0])
            res['purchase_line_ids'] = [(6, 0, purchase.order_line.ids)]
        return res

    def action_assign_project(self):
        """Assigner le projet aux lignes et recalculer analytic_distribution."""
        if not self.purchase_line_ids:
            raise UserError(_("Aucune ligne d'achat sélectionnée."))

        for line in self.purchase_line_ids:
            line.project_id = self.project_id
            line._compute_analytic_distribution()  # Recalcule auto

        return {
            'type': 'ir.actions.act_window_close'
        }
