from odoo import models


class TreasuryForecastXlsx(models.AbstractModel):
    _name = "report.treasury_management.treasury_forecast_xlsx"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, forecasts):
        sheet = workbook.add_worksheet("Prévisions")
        header = workbook.add_format({"bold": True})
        headers = [
            "Période",
            "Début",
            "Fin",
            "Source",
            "Référence",
            "Devise",
            "Montant devise",
            "Montant société",
        ]
        for col, title in enumerate(headers):
            sheet.write(0, col, title, header)
        row = 1
        for rec in forecasts:
            sheet.write(row, 0, rec.period_type or "")
            sheet.write(row, 1, str(rec.date or ""))
            sheet.write(row, 2, str(rec.date_end or ""))
            sheet.write(row, 3, rec.source_type or "")
            sheet.write(row, 4, rec.source_ref or "")
            sheet.write(row, 5, rec.currency_id.name or "")
            sheet.write(row, 6, rec.amount_currency or 0.0)
            sheet.write(row, 7, rec.amount or 0.0)
            row += 1
