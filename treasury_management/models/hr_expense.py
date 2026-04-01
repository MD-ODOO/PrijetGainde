from odoo import api, fields, models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    treasury_payment_id = fields.Many2one(
        "treasury.payment",
        string="Décaissement trésorerie",
        readonly=True,
        copy=False,
    )

    def action_sheet_move_create(self):
        res = super().action_sheet_move_create()
        self._sync_treasury_payment()
        return res

    def _sync_treasury_payment(self):
        Payment = self.env["treasury.payment"]
        threshold = Payment._get_cash_threshold()
        for sheet in self:
            # Montant en devise société (hr.expense.sheet total_amount est en devise société)
            amount = sheet.total_amount or 0.0
            currency = sheet.company_id.currency_id
            partner = (
                sheet.employee_id.address_home_id
                or sheet.employee_id.work_contact_id
                or sheet.employee_id.address_id
                or False
            )
            vals = {
                "payment_type": "expense",
                "partner_id": partner.id if partner else False,
                "currency_id": currency.id,
                "amount": amount,
                "amount_currency": amount,
                "payment_date": sheet.accounting_date or fields.Date.context_today(self),
                "planned_payment_date": sheet.accounting_date or fields.Date.context_today(self),
                "company_id": sheet.company_id.id,
                "state": "planned",
            }
            # Laisser payment_channel vide pour que le seuil caisse s'applique; si seuil atteint, forcer cash
            if amount < threshold:
                vals["payment_channel"] = "cash"

            if sheet.treasury_payment_id:
                # Mise à jour si déjà créé et non payé
                if sheet.treasury_payment_id.state != "paid":
                    sheet.treasury_payment_id.write(vals)
                continue

            payment = Payment.create(vals)
            sheet.treasury_payment_id = payment.id

    def action_cancel(self):
        res = super().action_cancel()
        for sheet in self.filtered("treasury_payment_id"):
            if sheet.treasury_payment_id.state != "paid":
                sheet.treasury_payment_id.unlink()
        return res
