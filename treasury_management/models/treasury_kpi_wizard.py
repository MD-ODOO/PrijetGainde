from datetime import date

from odoo import models, fields, api
from odoo.tools import date_utils
from odoo.tools.float_utils import float_round


class TreasuryKpi(models.Model):
    _name = "treasury.kpi"
    _description = "Indicateurs de trésorerie"

    date_from = fields.Date(
        required=True,
        default=lambda self: date_utils.start_of(fields.Date.context_today(self), "month"),
    )
    date_to = fields.Date(required=True, default=fields.Date.context_today)

    supplier_payment_rate = fields.Float(
        string="Taux de règlement fournisseurs (%)", compute="_compute_kpis", store=True
    )
    customer_collection_rate = fields.Float(
        string="Taux de recouvrement client (%)", compute="_compute_kpis", store=True
    )

    total_to_disburse = fields.Monetary(
        string="Montant global à décaisser", compute="_compute_kpis", store=True
    )
    total_salary = fields.Monetary(string="Salaires", compute="_compute_kpis", store=True)
    total_bonus = fields.Monetary(string="Primes", compute="_compute_kpis", store=True)
    total_supplier = fields.Monetary(string="Fournisseurs", compute="_compute_kpis", store=True)
    total_tax = fields.Monetary(string="Impôts et taxes", compute="_compute_kpis", store=True)
    total_expense = fields.Monetary(string="Notes de frais", compute="_compute_kpis", store=True)
    total_other = fields.Monetary(string="Autres décaissements", compute="_compute_kpis", store=True)

    total_receipt_forecast = fields.Monetary(
        string="Encaissements prévus", compute="_compute_kpis", store=True
    )
    total_receipt_customer = fields.Monetary(
        string="Clients (prévu)", compute="_compute_kpis", store=True
    )
    total_receipt_other = fields.Monetary(
        string="Autres encaissements (prévu)", compute="_compute_kpis", store=True
    )

    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, required=True
    )
    currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", readonly=True, store=True
    )

    # Champs pour filtres dynamiques
    category_id = fields.Many2one("treasury.category", string="Catégorie")
    user_id = fields.Many2one(
        "res.users", string="Utilisateur", default=lambda self: self.env.user
    )

    # Sélection d'un lot paie pour une période donnée
    payroll_batch_id = fields.Many2one(
        "treasury.payroll.batch",
        string="Lot paie",
        domain="[('company_id', '=', company_id)]",
        help="Choisissez un lot de paie ; la période sera pré‑remplie et les informations du lot seront affichées.",
    )
    batch_period_start = fields.Date(
        related="payroll_batch_id.period_start",
        string="Début lot",
        readonly=True,
        store=True,
    )
    batch_period_end = fields.Date(
        related="payroll_batch_id.period_end",
        string="Fin lot",
        readonly=True,
        store=True,
    )
    batch_amount_total = fields.Monetary(
        related="payroll_batch_id.amount_total",
        string="Montant lot",
        currency_field="currency_id",
        readonly=True,
        store=True,
    )
    batch_type = fields.Selection(
        related="payroll_batch_id.batch_type",
        string="Type lot",
        readonly=True,
        store=True,
    )
    batch_state = fields.Selection(
        related="payroll_batch_id.state",
        string="État lot",
        readonly=True,
        store=True,
    )

    def _sync_period_with_batch(self, vals, batch):
        """Force la période et la société à refléter le lot choisi."""
        if not batch:
            return vals
        vals = dict(vals)
        vals["company_id"] = batch.company_id.id
        vals["date_from"] = batch.period_start
        vals["date_to"] = batch.period_end
        return vals

    @api.model
    def create(self, vals):
        batch = vals.get("payroll_batch_id") and self.env["treasury.payroll.batch"].browse(vals["payroll_batch_id"])
        if batch:
            vals = self._sync_period_with_batch(vals, batch)
        return super().create(vals)

    def write(self, vals):
        if vals.get("payroll_batch_id"):
            batch = self.env["treasury.payroll.batch"].browse(vals["payroll_batch_id"])
            vals = self._sync_period_with_batch(vals, batch)
        res = super().write(vals)
        return res

    @api.onchange("payroll_batch_id")
    def _onchange_payroll_batch_id(self):
        """Quand un lot est choisi, aligner période et société sur ce lot."""
        for record in self:
            batch = record.payroll_batch_id
            if not batch:
                continue
            record.company_id = batch.company_id
            record.date_from = batch.period_start
            record.date_to = batch.period_end

    @api.model
    def _percentage(self, numerator, denominator):
        """Return a percentage (0-100) rounded to 2 digits, safe for zero or negative sums."""
        denominator = abs(denominator or 0.0)
        numerator = abs(numerator or 0.0)
        return float_round((numerator / denominator) * 100.0, precision_digits=2) if denominator else 0.0

    @api.model
    def _aggregate_invoice_amounts(self, domain):
        """
        Aggregate invoice totals in company currency with partial payments handled.

        Returns (total, paid, residual) as positive amounts.
        """
        grouped = self.env["account.move"].read_group(
            domain,
            ["amount_total_signed", "amount_residual_signed"],
            [],
        )
        if not grouped:
            return 0.0, 0.0, 0.0
        totals = grouped[0]
        total = totals.get("amount_total_signed") or 0.0
        residual = totals.get("amount_residual_signed") or 0.0
        paid = total - residual
        return total, paid, residual

    @api.model
    def _aggregate_payments(self, date_from, date_to, company):
        """Agrège les décaissements à payer (états draft/planned) par type sur la période."""
        payments = self.env["treasury.payment"].search(
            [
                ("company_id", "=", company.id),
                ("state", "in", ("draft", "planned")),  # only unpaid / à payer
            ]
        )
        expected_keys = ("salary", "bonus", "supplier", "tax", "expense", "other")
        totals_by_type = {key: 0.0 for key in expected_keys}
        total = 0.0
        for payment in payments:
            ref_date = payment.planned_payment_date or payment.payment_date
            if not ref_date or ref_date < date_from or ref_date > date_to:
                continue
            amount = payment.amount or 0.0
            total += amount
            ptype = payment.payment_type or "other"
            totals_by_type[ptype] = totals_by_type.get(ptype, 0.0) + amount
        return total, totals_by_type

    @api.model
    def _aggregate_receipts(self, date_from, date_to, company):
        """Agrège les encaissements à recevoir : factures clients non payées (résiduel) + autres reçus non encaissés."""
        # Clients : factures postées non payées (inclut partiel) sur la période
        invoices = self.env["account.move"].search(
            [
                ("company_id", "=", company.id),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("payment_state", "!=", "paid"),
                ("invoice_date", ">=", date_from),
                ("invoice_date", "<=", date_to),
            ]
        )
        # Total attendu = montant facture (pas seulement le résiduel)
        customer_total = sum(abs(inv.amount_total_signed) for inv in invoices)

        # Autres encaissements prévus (type other) non encaissés
        other_receipts = self.env["treasury.receipt"].search(
            [
                ("company_id", "=", company.id),
                ("receipt_type", "=", "other"),
                ("state", "in", ("draft", "partial")),
                ("planned_receipt_date", ">=", date_from),
                ("planned_receipt_date", "<=", date_to),
            ]
        )
        other_total = sum(rec.amount or 0.0 for rec in other_receipts)

        total = customer_total + other_total
        totals_by_type = {"customer": customer_total, "other": other_total}
        return total, totals_by_type

    @api.model
    def _compute_supplier_payment_rate(self, date_from, date_to, company):
        """Calculate supplier payment rate based on treasury payments lifecycle.

        Rate = montant payé / (montant payé + montants en draft/planifié)
        over the selected period using planned_payment_date when available
        (fallback to payment_date).
        """

        payments = self.env["treasury.payment"].search(
            [
                ("payment_type", "=", "supplier"),
                ("state", "in", ("draft", "planned", "paid")),
                ("company_id", "=", company.id),
            ]
        )

        total_amount = 0.0
        paid_amount = 0.0

        for payment in payments:
            reference_date = (
                payment.payment_date if payment.state == "paid" else payment.planned_payment_date or payment.payment_date
            )
            if not reference_date:
                continue
            if reference_date < date_from or reference_date > date_to:
                continue

            amount = payment.amount or 0.0
            total_amount += amount
            if payment.state == "paid":
                paid_amount += amount

        return self._percentage(paid_amount, total_amount)

    @api.model
    def _compute_customer_collection_rate(self, date_from, date_to, company):
        """Calculate customer collection rate based on treasury receipts lifecycle.

        Rate = encaissé / (encaissé + brouillon + validé manager + validé)
        on the period, using planned_receipt_date when available (fallback to receipt_date).
        """

        receipts = self.env["treasury.receipt"].search(
            [
                ("receipt_type", "=", "customer"),
                ("state", "in", ("draft", "manager_approved", "approved", "paid")),
                ("company_id", "=", company.id),
            ]
        )

        total_amount = 0.0
        paid_amount = 0.0

        for receipt in receipts:
            reference_date = (
                receipt.receipt_date if receipt.state == "paid" else receipt.planned_receipt_date or receipt.receipt_date
            )
            if not reference_date:
                continue
            if reference_date < date_from or reference_date > date_to:
                continue

            amount = receipt.amount or 0.0
            total_amount += amount
            if receipt.state == "paid":
                paid_amount += amount

        return self._percentage(paid_amount, total_amount)

    @api.depends("date_from", "date_to", "company_id")
    def _compute_kpis(self):
        for record in self:
            metrics = self._compute_metrics(
                record.date_from,
                record.date_to,
                record.company_id,
            )
            record.supplier_payment_rate = metrics["supplier_payment_rate"]
            record.customer_collection_rate = metrics["customer_collection_rate"]
            record.total_to_disburse = metrics["total_to_disburse"]
            record.total_salary = metrics["total_salary"]
            record.total_bonus = metrics["total_bonus"]
            record.total_supplier = metrics["total_supplier"]
            record.total_tax = metrics["total_tax"]
            record.total_expense = metrics["total_expense"]
            record.total_other = metrics["total_other"]
            record.total_receipt_forecast = metrics["total_receipt_forecast"]
            record.total_receipt_customer = metrics["total_receipt_customer"]
            record.total_receipt_other = metrics["total_receipt_other"]

    @api.model
    def _compute_metrics(self, date_from, date_to, company):
        """Retourne les indicateurs KPI pour la période et la société données."""
        date_from = date_from or date_utils.start_of(fields.Date.context_today(self), "month")
        date_to = date_to or fields.Date.context_today(self)
        company = company or self.env.company

        # Ensure the range is coherent (swap if user inverted the dates)
        if date_from and date_to and date_from > date_to:
            date_from, date_to = date_to, date_from

        supplier_payment_rate = self._compute_supplier_payment_rate(date_from, date_to, company)
        customer_collection_rate = self._compute_customer_collection_rate(date_from, date_to, company)

        total_to_disburse, totals_by_type = self._aggregate_payments(date_from, date_to, company)
        total_receipts, receipts_by_type = self._aggregate_receipts(date_from, date_to, company)

        return {
            "supplier_payment_rate": supplier_payment_rate,
            "customer_collection_rate": customer_collection_rate,
            "total_to_disburse": total_to_disburse,
            "total_salary": totals_by_type.get("salary", 0.0),
            "total_bonus": totals_by_type.get("bonus", 0.0),
            "total_supplier": totals_by_type.get("supplier", 0.0),
            "total_tax": totals_by_type.get("tax", 0.0),
            "total_expense": totals_by_type.get("expense", 0.0),
            "total_other": totals_by_type.get("other", 0.0),
            "total_receipt_forecast": total_receipts,
            "total_receipt_customer": receipts_by_type.get("customer", 0.0),
            "total_receipt_other": receipts_by_type.get("other", 0.0),
        }

    @api.model
    def get_dashboard_data(self, year=None, company_id=None):
        """Return aggregate KPIs and a monthly series for the dashboard client action."""
        # Normalize dates
        today = fields.Date.context_today(self)
        year = int(year or today.year)
        start = date(year, 1, 1)
        end = date(year, 12, 31)

        env_sudo = self.sudo()
        company = env_sudo["res.company"].browse(company_id) if company_id else env_sudo.company

        def _collect_payment_stats():
            payments = env_sudo["treasury.payment"].search(
                [
                    ("company_id", "=", company.id),
                    ("state", "in", ("draft", "planned", "paid")),
                ]
            )
            stats = {
                "total_amount": 0.0,
                "paid_amount": 0.0,
                "planned_amount": 0.0,
                "total_count": 0,
                "paid_count": 0,
                "pending_count": 0,
                "overdue_count": 0,
            }
            for payment in payments:
                ref_date = (
                    payment.payment_date
                    if payment.state == "paid"
                    else payment.planned_payment_date or payment.payment_date
                )
                if not ref_date or ref_date < start or ref_date > end:
                    continue

                amount = payment.amount or 0.0
                stats["total_amount"] += amount
                stats["total_count"] += 1

                if payment.state == "paid":
                    stats["paid_amount"] += amount
                    stats["paid_count"] += 1
                else:
                    stats["planned_amount"] += amount
                    if ref_date < today:
                        stats["overdue_count"] += 1
                    else:
                        stats["pending_count"] += 1

            stats["paid_rate"] = self._percentage(stats["paid_amount"], stats["total_amount"])
            stats["overdue_rate"] = self._percentage(stats["overdue_count"], stats["total_count"])
            return stats

        def _collect_receipt_stats():
            # Open customer invoices (unpaid or partially paid)
            inv_domain_stats = [
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("state", "=", "posted"),
                ("payment_state", "!=", "paid"),
                ("invoice_date", ">=", start),
                ("invoice_date", "<=", end),
                ("company_id", "=", company.id),
            ]
            invoices = env_sudo["account.move"].search(inv_domain_stats)
            stats = {
                "total_amount": 0.0,
                "paid_amount": 0.0,
                "planned_amount": 0.0,
                "total_count": 0,
                "paid_count": 0,
                "pending_count": 0,
                "overdue_count": 0,
            }
            for inv in invoices:
                due = inv.invoice_date_due or inv.invoice_date or start
                amount = abs(inv.amount_total_signed)  # full invoice amount (unpaid or partially paid)
                stats["total_amount"] += amount
                stats["planned_amount"] += amount
                stats["total_count"] += 1
                if due < today:
                    stats["overdue_count"] += 1
                else:
                    stats["pending_count"] += 1

            stats["paid_rate"] = self._percentage(stats["paid_amount"], stats["total_amount"])
            stats["overdue_rate"] = self._percentage(stats["overdue_count"], stats["total_count"])
            return stats

        payment_stats = _collect_payment_stats()
        receipt_stats = _collect_receipt_stats()

        # Revenues (customer invoices)
        inv_domain = [
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
            ("company_id", "=", company.id),
        ]
        invoices = env_sudo["account.move"].read_group(
            inv_domain, ["amount_total_signed"], ["invoice_date:month"]
        )
        revenue_total = sum((line.get("amount_total_signed") or 0.0) for line in invoices)
        revenue_by_month = {}
        for line in invoices:
            group_value = line.get("invoice_date:month")
            if not group_value:
                continue
            group_date = (
                fields.Date.from_string(group_value)
                if isinstance(group_value, str)
                else group_value
            )
            revenue_by_month[group_date.month] = revenue_by_month.get(group_date.month, 0.0) + (
                line.get("amount_total_signed") or 0.0
            )

        # Receivables (open customer invoices)
        receivables = env_sudo["account.move"].search(inv_domain + [("payment_state", "!=", "paid")])
        receivables_amount = sum(receivables.mapped("amount_residual_signed"))

        # Expenses (vendor bills)
        bill_domain = [
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("state", "=", "posted"),
            ("invoice_date", ">=", start),
            ("invoice_date", "<=", end),
            ("company_id", "=", company.id),
        ]
        bills = env_sudo["account.move"].read_group(
            bill_domain, ["amount_total_signed"], ["invoice_date:month"]
        )
        expenses_total = sum((line.get("amount_total_signed") or 0.0) for line in bills)
        expenses_by_month = {}
        for line in bills:
            group_value = line.get("invoice_date:month")
            if not group_value:
                continue
            group_date = (
                fields.Date.from_string(group_value)
                if isinstance(group_value, str)
                else group_value
            )
            expenses_by_month[group_date.month] = expenses_by_month.get(group_date.month, 0.0) + (
                line.get("amount_total_signed") or 0.0
            )

        # Debts (open vendor bills)
        debts = env_sudo["account.move"].search(bill_domain + [("payment_state", "!=", "paid")])
        debts_amount = sum(debts.mapped("amount_residual_signed"))

        # Build monthly cumulative series
        months = list(range(1, 13))
        revenue_series = []
        expense_series = []
        cumulative = 0.0
        cumulative_exp = 0.0
        for month in months:
            monthly_rev = revenue_by_month.get(month, 0.0)
            cumulative += monthly_rev
            revenue_series.append({"label": month, "value": monthly_rev, "cumulative": cumulative})

            monthly_exp = expenses_by_month.get(month, 0.0)
            cumulative_exp += monthly_exp
            expense_series.append({"label": month, "value": monthly_exp, "cumulative": cumulative_exp})

        return {
            "year": year,
            "company": {
                "id": company.id,
                "name": company.name,
                "currency_id": company.currency_id.id,
                "currency_symbol": company.currency_id.symbol,
                "currency_position": company.currency_id.position,
            },
            "summary": {
                "revenue": revenue_total,
                "receivables": receivables_amount,
                "expenses": expenses_total,
                "debts": debts_amount,
                "payments_total": payment_stats["total_amount"],
                "payments_paid": payment_stats["paid_amount"],
                "receipts_total": receipt_stats["total_amount"],
                "receipts_paid": receipt_stats["paid_amount"],
                "cash_gap": receipt_stats["total_amount"] - payment_stats["total_amount"],
            },
            "series": {
                "revenue": revenue_series,
                "expenses": expense_series,
            },
            "payments": payment_stats,
            "receipts": receipt_stats,
        }

    def action_print_kpi(self):
        """Print the KPI report for this record's period and company."""
        self.ensure_one()
        data = {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "company_id": self.company_id.id,
        }
        return self.env.ref("treasury_management.treasury_kpi_report").report_action(
            self, data=data
        )
