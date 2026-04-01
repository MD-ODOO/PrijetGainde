from odoo import api, fields, models, _
from odoo.exceptions import UserError


class TreasuryPayrollOrderWizard(models.TransientModel):
    _name = "treasury.payroll.order.wizard"
    _description = "Ordre de décaissement paie"

    batch_id = fields.Many2one(
        "treasury.payroll.batch", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one(
        "res.company",
        related="batch_id.company_id",
        store=False,
        readonly=True,
    )
    payment_date = fields.Date(
        string="Date de paiement",
        default=fields.Date.context_today,
        required=True,
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Journal",
        required=True,
        domain="[('type','in',('bank','cash')),('company_id','=',company_id)]",
    )
    partner_id = fields.Many2one("res.partner", string="Bénéficiaire", required=True)
    payment_channel = fields.Selection(
        [("transfer", "Virement"), ("cheque", "Chèque"), ("cash", "Espèces")],
        string="Mode de paiement",
        default="transfer",
        required=True,
    )
    note = fields.Text(string="Instructions")

    def action_create(self):
        self.ensure_one()
        batch = self.batch_id
        if not batch or not batch.amount_total:
            raise UserError(_("Lot de paie vide."))

        Payment = self.env["treasury.payment"]
        payment_type = "salary" if batch.batch_type in ("42", "422") else "supplier"
        if batch.batch_type == "44":
            payment_type = "tax"

        vals = {
            "payment_type": payment_type,
            "partner_id": self.partner_id.id,
            "currency_id": batch.currency_id.id,
            "amount_currency": batch.amount_total,
            "payment_date": self.payment_date,
            "planned_payment_date": self.payment_date,
            "payment_channel": self.payment_channel,
            "journal_id": self.journal_id.id,
            "instructions": self.note,
            "state": "planned",
            "company_id": batch.company_id.id,
            "payroll_batch_id": batch.id,
        }

        # Reuse existing treasury payment if not paid
        if batch.payroll_payment_id and batch.payroll_payment_id.state != "paid":
            batch.payroll_payment_id.write(vals)
            payment = batch.payroll_payment_id
        else:
            payment = Payment.create(vals)
            batch.payroll_payment_id = payment.id

        return {
            "type": "ir.actions.act_window",
            "res_model": "treasury.payment",
            "res_id": payment.id,
            "view_mode": "form",
        }
