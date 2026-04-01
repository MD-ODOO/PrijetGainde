from odoo import models, fields, _
from odoo.exceptions import UserError


class TreasuryPaymentScheduleWizard(models.TransientModel):
    _name = "treasury.payment.schedule.wizard"
    _description = "Planifier un décaissement"

    invoice_id = fields.Many2one(
        "account.move",
        required=True,
        domain=[("move_type", "=", "in_invoice")],
    )
    partner_id = fields.Many2one("res.partner", string="Fournisseur", readonly=True)
    planned_payment_date = fields.Date(string="Date prévue", required=True)
    payment_channel = fields.Selection(
        [("transfer", "Virement"), ("cheque", "Chèque"), ("cash", "Espèces")],
        string="Mode de paiement",
        required=True,
    )
    priority = fields.Selection(
        [("0", "Basse"), ("1", "Normale"), ("2", "Haute"), ("3", "Urgente")],
        default="1",
        required=True,
    )
    category_id = fields.Many2one("treasury.category", string="Catégorie")
    instructions = fields.Text(string="Directives")

    def action_schedule(self):
        self.ensure_one()
        if self.invoice_id.payment_state == "paid":
            raise UserError("La facture est déjà payée.")
        Payment = self.env["treasury.payment"]
        vals = {
            "planned_payment_date": self.planned_payment_date,
            "payment_channel": self.payment_channel,
            "priority": self.priority,
            "category_id": self.category_id.id,
            "instructions": self.instructions,
            "state": "planned",
        }
        payment = Payment.search([
            ("invoice_id", "=", self.invoice_id.id),
            ("state", "!=", "paid"),
        ], limit=1)
        if payment:
            payment.write(vals)
        else:
            vals.update({
                "invoice_id": self.invoice_id.id,
                "partner_id": self.invoice_id.partner_id.id,
                "currency_id": self.invoice_id.currency_id.id,
                "amount_currency": self.invoice_id.amount_residual or self.invoice_id.amount_total,
                "payment_type": "supplier",
            })
            payment = Payment.create(vals)
        self.env.user.notify_info(
            message=_("Décaissement planifié pour le %s.") % (self.planned_payment_date,),
            title=_("Décaissement programmé"),
            sticky=False,
        )
        return {"type": "ir.actions.act_window_close"}
