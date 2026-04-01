from odoo import api, fields, models, _


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def action_payslip_done(self):
        res = super().action_payslip_done()
        batches = self.env["treasury.payroll.batch"]
        for slip in self:
            batches._generate_batches_for_period(
                slip.date_from,
                slip.date_to,
                slip.company_id,
            )
        self._sync_treasury_salary_payment()
        return res

    def _sync_treasury_salary_payment(self):
        Payment = self.env["treasury.payment"]
        threshold = Payment._get_cash_threshold()
        for slip in self:
            net_line = slip.line_ids.filtered(lambda l: l.code == "NET")[:1]
            net_amount = abs(net_line.total) if net_line else 0.0
            if not net_amount:
                continue

            partner = (
                slip.employee_id.address_home_id
                or slip.employee_id.work_contact_id
                or slip.employee_id.address_id
                or False
            )

            vals = {
                "payment_type": "salary",
                "employee_id": slip.employee_id.id,
                "partner_id": partner.id if partner else False,
                "currency_id": slip.company_id.currency_id.id,
                "amount_currency": net_amount,
                "payment_date": slip.date_to or slip.date_from or fields.Date.context_today(self),
                "planned_payment_date": slip.date_to or slip.date_from or fields.Date.context_today(self),
                "company_id": slip.company_id.id,
                "state": "planned",
                "payslip_id": slip.id,
            }

            if net_amount < threshold:
                vals["payment_channel"] = "cash"
            else:
                vals["payment_channel"] = "transfer"

            if slip.treasury_payment_id:
                # If payment already paid, don't override it
                if slip.treasury_payment_id.state != "paid":
                    slip.treasury_payment_id.write(vals)
                continue

            payment = Payment.create(vals)
            slip.treasury_payment_id = payment.id

    treasury_payment_id = fields.Many2one(
        "treasury.payment",
        string="Décaissement trésorerie",
        readonly=True,
        copy=False,
    )
