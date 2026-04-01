from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    cost_amount = fields.Monetary(compute='_compute_cost_amount', store=True,
                                  string='Coût Valorisé')

    @api.depends('unit_amount', 'employee_id.hourly_cost')
    def _compute_cost_amount(self):
        for line in self:
            line.cost_amount = line.unit_amount * (
                line.employee_id.hourly_cost or 0)

    @api.constrains('project_id', 'task_id', 'timesheet_invoice_type')
    def _check_timesheet_required(self):
        for line in self:
            if line.project_id and not line.unit_amount:
                raise ValidationError(
                    _("La saisie des temps est obligatoire pour ce projet/tâche."))



