from odoo import models, fields, api
from odoo.tools import date_utils

class TreasuryForecast(models.Model):
    _name = "treasury.forecast"
    _description = "Prévision de trésorerie"
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        string="Société",
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
        string="Devise",
    )
    date = fields.Date(string="Date de période")
    period_type = fields.Selection(
        [("month", "Mensuel"), ("quarter", "Trimestriel")],
        default="month",
        required=True,
        string="Type de période",
    )
    date_end = fields.Date(string="Date de fin", compute="_compute_date_end", store=True)
    amount_currency = fields.Monetary(currency_field="currency_id", string="Montant (devise)")
    amount = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_amount",
        inverse="_inverse_amount",
        store=True,
        string="Montant",
    )
    flow_direction = fields.Selection(
        [("in", "Encaissement"), ("out", "Décaissement")],
        default="out",
        required=True,
        string="Flux",
    )
    signed_amount_currency = fields.Monetary(
        currency_field="currency_id",
        compute="_compute_signed_amount",
        store=True,
        string="Montant net (devise)",
    )
    signed_amount = fields.Monetary(
        currency_field="company_currency_id",
        compute="_compute_signed_amount",
        store=True,
        string="Montant net",
    )
    source_type = fields.Selection(
        [
            ("manual", "Saisie manuelle"),
            ("invoice", "Facture fournisseur"),
            ("purchase", "Bon de commande"),
            ("payroll", "Salaire"),
            ("payment", "Décaissement"),
            ("receipt", "Encaissement"),
        ],
        default="manual",
        required=True,
        string="Type de source",
    )
    source_ref = fields.Char(string="Référence source")
    priority = fields.Selection(
        [("0", "Basse"), ("1", "Normale"), ("2", "Haute"), ("3", "Urgente")],
        default="1",
        string="Priorité",
    )

    @api.depends("date", "period_type")
    def _compute_date_end(self):
        for rec in self:
            if not rec.date:
                rec.date_end = False
                continue
            if rec.period_type == "quarter":
                rec.date_end = date_utils.end_of(rec.date, "quarter")
            else:
                rec.date_end = date_utils.end_of(rec.date, "month")

    @api.depends("amount_currency", "currency_id", "company_id", "date")
    def _compute_amount(self):
        for rec in self:
            if not rec.currency_id or not rec.company_currency_id:
                rec.amount = rec.amount_currency or 0.0
                continue
            if rec.currency_id == rec.company_currency_id:
                rec.amount = rec.amount_currency or 0.0
            else:
                rec.amount = rec.currency_id._convert(
                    rec.amount_currency or 0.0,
                    rec.company_currency_id,
                    rec.company_id,
                    rec.date or fields.Date.context_today(rec),
                )

    def _inverse_amount(self):
        for rec in self:
            if not rec.currency_id or not rec.company_currency_id:
                rec.amount_currency = rec.amount
                continue
            if rec.currency_id == rec.company_currency_id:
                rec.amount_currency = rec.amount
            else:
                rec.amount_currency = rec.company_currency_id._convert(
                    rec.amount or 0.0,
                    rec.currency_id,
                    rec.company_id,
                    rec.date or fields.Date.context_today(rec),
                )

    @api.onchange("source_type")
    def _onchange_source_type_flow_direction(self):
        for rec in self:
            if rec.source_type == "receipt":
                rec.flow_direction = "in"
            elif rec.source_type:
                rec.flow_direction = "out"

    @api.depends("amount_currency", "amount", "flow_direction", "currency_id", "company_currency_id")
    def _compute_signed_amount(self):
        for rec in self:
            sign = 1 if rec.flow_direction == "in" else -1
            rec.signed_amount_currency = sign * (rec.amount_currency or 0.0)
            rec.signed_amount = sign * (rec.amount or 0.0)

    @api.model
    def generate_from_sources(self, start_date, end_date, period_type="month"):
        Forecast = self.env["treasury.forecast"].sudo()

        def _period_start(dt):
            """Return the start of the chosen period (month or quarter) for a given date."""
            if not dt:
                return dt
            return date_utils.start_of(dt, period_type)

        # Purge previously generated (non manuels) forecasts in the window to avoid duplicates
        Forecast.search([
            ("date", ">=", start_date),
            ("date", "<=", end_date),
            ("source_type", "!=", "manual"),
        ]).unlink()

        # Vendor bills
        bills = self.env["account.move"].sudo().search([
            ("move_type", "=", "in_invoice"),
            ("payment_state", "!=", "paid"),
            ("invoice_date_due", ">=", start_date),
            ("invoice_date_due", "<=", end_date),
        ])
        for bill in bills:
            period_date = _period_start(bill.invoice_date_due or bill.invoice_date)
            Forecast.create({
                "date": period_date,
                "period_type": period_type,
                "currency_id": bill.currency_id.id,
                "amount_currency": bill.amount_residual,
                "source_type": "invoice",
                "source_ref": bill.name or bill.ref,
                "flow_direction": "out",
            })

        # Purchase orders to invoice
        purchase_orders = self.env["purchase.order"].sudo().search([
            ("state", "in", ["purchase", "done"]),
            ("date_order", ">=", start_date),
            ("date_order", "<=", end_date),
        ])
        for po in purchase_orders:
            amount_to_invoice = getattr(po, "amount_to_invoice", 0.0) or 0.0
            if amount_to_invoice <= 0.0:
                continue
            period_date = _period_start(po.date_order.date() if po.date_order else start_date)
            Forecast.create({
                "date": period_date,
                "period_type": period_type,
                "currency_id": po.currency_id.id,
                "amount_currency": amount_to_invoice,
                "source_type": "purchase",
                "source_ref": po.name,
                "flow_direction": "out",
            })

        # Payroll slips
        slips = self.env["hr.payslip"].sudo().search([
            ("state", "in", ["draft", "verify"]),
            ("date_to", ">=", start_date),
            ("date_to", "<=", end_date),
        ])
        for slip in slips:
            net_line = slip.line_ids.filtered(lambda l: l.code == "NET")[:1]
            net_amount = net_line.total if net_line else 0.0
            period_date = _period_start(slip.date_to)
            Forecast.create({
                "date": period_date,
                "period_type": period_type,
                "currency_id": slip.company_id.currency_id.id,
                "amount_currency": net_amount,
                "source_type": "payroll",
                "source_ref": slip.number or slip.name,
                "flow_direction": "out",
            })

        # Treasury payments (planned)
        payments = self.env["treasury.payment"].sudo().search([
            ("state", "!=", "paid"),
            ("planned_payment_date", ">=", start_date),
            ("planned_payment_date", "<=", end_date),
        ])
        for pay in payments:
            period_date = _period_start(pay.planned_payment_date)
            Forecast.create({
                "date": period_date,
                "period_type": period_type,
                "currency_id": pay.currency_id.id,
                "amount_currency": pay.amount_currency,
                "source_type": "payment",
                "source_ref": pay.name,
                "priority": pay.priority,
                "flow_direction": "out",
            })

        # Treasury receipts (planned)
        receipts = self.env["treasury.receipt"].sudo().search([
            ("state", "!=", "paid"),
            ("planned_receipt_date", ">=", start_date),
            ("planned_receipt_date", "<=", end_date),
        ])
        for rec in receipts:
            period_date = _period_start(rec.planned_receipt_date)
            Forecast.create({
                "date": period_date,
                "period_type": period_type,
                "currency_id": rec.currency_id.id,
                "amount_currency": rec.amount_currency,
                "source_type": "receipt",
                "source_ref": rec.name,
                "priority": rec.priority,
                "flow_direction": "in",
            })

    @api.model
    def _cron_treasury_forecast_alert(self):
        param = self.env["ir.config_parameter"].sudo()
        try:
            threshold = float(param.get_param("treasury_management.alert_threshold", default="0"))
        except ValueError:
            threshold = 0.0
        try:
            days = int(param.get_param("treasury_management.alert_days", default="30"))
        except ValueError:
            days = 30
        start_date = fields.Date.context_today(self)
        end_date = date_utils.add(start_date, days=days)
        forecasts = self.search([
            ("date", ">=", start_date),
            ("date", "<=", end_date),
        ])
        if not forecasts:
            return
        total = sum(forecasts.mapped("amount"))
        if total >= threshold:
            return
        users = self.env.ref("treasury_management.group_treasury_df").users
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for user in users:
            forecasts[0].activity_schedule(
                activity_type.id,
                user_id=user.id,
                summary="Alerte trésorerie",
                note=f"Solde prévisionnel {total:.2f} sous le seuil {threshold:.2f}.",
            )
