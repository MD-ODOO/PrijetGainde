from odoo import models, fields
from odoo.tools import date_utils


class ReportTreasuryKpi(models.AbstractModel):
    _name = "report.treasury_management.treasury_kpi_template"
    _description = "Treasury KPI Report"

    def _get_report_values(self, docids, data=None):
        data = data or {}
        date_from = data.get("date_from")
        date_to = data.get("date_to")
        company_id = data.get("company_id")

        if not date_from or not date_to:
            today = fields.Date.context_today(self)
            date_from = date_utils.start_of(today, "month")
            date_to = today

        company = self.env["res.company"].browse(company_id) if company_id else self.env.company

        metrics = self.env["treasury.kpi"]._compute_metrics(date_from, date_to, company)

        return {
            "doc_ids": docids,
            "doc_model": "account.move",
            "docs": self.env["account.move"].browse(docids),
            "date_from": date_from,
            "date_to": date_to,
            "company": company,
            "supplier_payment_rate": metrics["supplier_payment_rate"],
            "customer_collection_rate": metrics["customer_collection_rate"],
            "total_to_disburse": metrics["total_to_disburse"],
            "totals_by_type": {
                "salary": metrics["total_salary"],
                "bonus": metrics["total_bonus"],
                "supplier": metrics["total_supplier"],
                "tax": metrics["total_tax"],
            },
        }
