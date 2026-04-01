from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    project_id = fields.Many2one('project.project', string="Projet Associé",
                                 store=True,
                                 help="Sélectionnez le projet pour imputer automatiquement les coûts analytiques."
                                 )

    @api.onchange('project_id')
    def _onchange_project_id(self):
        """Remplit automatiquement la distribution analytique quand un projet est sélectionné
            À GERER À LA DEMANDE DU CLIENT:
                # elif self.project_id and project_type == 'poc':
                #     self.analytic_distribution = False
        """
        for line in self:
            if line.project_id:
                if line.project_id.account_id:
                    line.analytic_distribution = {
                        str(line.project_id.account_id.id): 100.0
                    }
                else:
                    line.analytic_distribution = False

                    return {
                        'warning': {
                            'title': _("Information Analytique"),
                            'message': _(
                                "Le projet '%s' n'a pas de compte analytique lié. "
                                "La distribution analytique ne peut pas être automatisée."
                            ) % line.project_id.name
                        }
                    }
            else:
                # Si le projet est retiré, on vide la distribution
                line.analytic_distribution = False

    @api.constrains('project_id', 'analytic_distribution')
    def _check_analytic_for_project(self):
        """Validation : si projet présent → distribution analytique obligatoire"""
        for line in self:
            if line.project_id and not line.analytic_distribution:
                raise ValidationError(
                    _("Une distribution analytique est obligatoire quand un projet est associé à la ligne d'achat.")
                )
            # OPTION vérifier que la somme fait 100%
            if line.analytic_distribution:
                total_pct = sum(line.analytic_distribution.values())
                if abs(total_pct - 100.0) > 0.01:
                    raise ValidationError(
                        _("La distribution analytique du projet %s doit totaliser 100%% (Actuel: %s%%).")
                        % (line.project_id.name, total_pct))

    def action_assign_project_wizard(self):
        """ button pour assigner plusieurs lignes d'achat via le wizard"""
        return {
            'name': "Assigner un Projet",
            'type': 'ir.actions.act_window',
            'res_model': 'assign.project.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_purchase_id': self.id}
        }
