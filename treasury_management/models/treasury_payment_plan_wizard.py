from odoo import models, fields, api, _
from odoo.exceptions import UserError


class TreasuryPaymentPlanWizard(models.TransientModel):
    _name = "treasury.payment.plan.wizard"
    _description = "Planifier des décaissements"

    payment_ids = fields.Many2many(
        "treasury.payment",
        string="Décaissements",
        readonly=True,
        default=lambda self: self.env.context.get("default_payment_ids"),
    )
    planned_payment_date = fields.Date(
        string="Date prévue",
        required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    payment_channel = fields.Selection(
        [("transfer", "Virement"), ("cheque", "Chèque"), ("cash", "Espèces")],
        string="Mode de paiement",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal de paiement",
        domain="[('type', 'in', ['bank','cash'])]",
    )
    priority = fields.Selection(
        [("0", "Basse"), ("1", "Normale"), ("2", "Haute"), ("3", "Urgente")],
        default="1",
        string="Priorité",
    )
    instructions = fields.Text(string="Instructions")

    @api.onchange("payment_channel")
    def _onchange_payment_channel(self):
        domain = []
        if self.payment_channel in ("transfer", "cheque"):
            domain = [("type", "=", "bank")]
        elif self.payment_channel == "cash":
            domain = [("type", "=", "cash")]
        return {"domain": {"journal_id": domain}}

    def action_apply(self):
        self.ensure_one()
        payments = self.payment_ids
        if not payments:
            raise UserError(_("Aucun décaissement sélectionné."))

        vals = {
            "planned_payment_date": self.planned_payment_date,
            "priority": self.priority,
        }
        if self.payment_channel:
            vals["payment_channel"] = self.payment_channel
        if self.journal_id:
            vals["journal_id"] = self.journal_id.id
        if self.instructions:
            vals["instructions"] = self.instructions

        for payment in payments:
            write_vals = vals.copy()
            # Harmoniser la date opérationnelle si absente
            if not payment.payment_date:
                write_vals["payment_date"] = self.planned_payment_date
            payment.write(write_vals)
            # Passer à l'état planifié
            if payment.state == "draft":
                payment.action_process()

        return {"type": "ir.actions.act_window_close"}

