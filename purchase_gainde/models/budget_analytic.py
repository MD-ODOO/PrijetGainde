from odoo import models, fields, _
from odoo.exceptions import UserError


class BudgetAnalytic(models.Model):
    _inherit = "budget.analytic"

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        required=True,
        help="Department linked to this budget",
    )

    # Montant validé (snapshot de budget_amount au moment de la révision)
    #budget_revised = fields.Float(string="Validé")

    # def fields_get(self, allfields=None, attributes=None):
    #     """Ajuste le libellé de l'état *confirmed* en *Validé*.

    #     On ne touche pas à la définition du champ, uniquement au libellé
    #     présenté dans l'UI pour la valeur 'confirmed'.
    #     """

    #     res = super().fields_get(allfields=allfields, attributes=attributes)
    #     state_info = res.get("state")
    #     if state_info and state_info.get("selection"):
    #         new_selection = []
    #         for key, label in state_info["selection"]:
    #             if key == "confirmed":
    #                 label = "Validé"
    #             new_selection.append((key, label))
    #         state_info["selection"] = new_selection
    #     return res

    # def write(self, vals):
    #     """Rend le budget en lecture seule une fois révisé.

    #     - Lorsque ``state = 'revised'``, on interdit toute modification
    #       des champs autres que ``state`` lui‑même.
    #     - Cela bloque l'édition depuis l'UI tout en laissant la
    #       possibilité à du code technique de changer l'état via le
    #       contexte si nécessaire.
    #     """

    #     protected_fields = set(vals.keys()) - {"state"}
    #     if protected_fields:
    #         for rec in self:
    #             if rec.state == "revised" and not self.env.context.get(
    #                 "gainde_allow_revised_write"
    #             ):
    #                 raise UserError(
    #                     _(
    #                         "Ce budget est révisé et n'est plus modifiable."
    #                     )
    #                 )

    #     return super().write(vals)
