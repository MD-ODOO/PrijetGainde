from odoo import models, fields


class BudgetReviseConfirmWizard(models.TransientModel):
    _name = "budget.revise.confirm.wizard"
    _description = "Confirm Budget Revision"

    budget_id = fields.Many2one(
        "budget.analytic",
        string="Budget",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.budget_id:
            return {"type": "ir.actions.act_window_close"}

        # Snapshot des montants validés avant révision, ligne par ligne
        # On pose la valeur actuelle de budget_amount dans revised_budget
        # sur le budget d'origine, ainsi elle sera copiée sur le budget
        # révisé créé par create_revised_budget.
        for line in self.budget_id.budget_line_ids:
            line.revised_budget = line.budget_amount

        # Appelle la méthode standard qui crée le budget révisé
        # et renvoie l'action d'ouverture des budgets révisés
        action = self.budget_id.create_revised_budget()
        return action
