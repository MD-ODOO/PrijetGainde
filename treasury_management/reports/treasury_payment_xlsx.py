from odoo import models


class TreasuryPaymentXlsx(models.AbstractModel):
    _name = "report.treasury_management.treasury_payment_xlsx"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, payments):
        sheet = workbook.add_worksheet("Décaissements")
        header = workbook.add_format({"bold": True})
        headers = [
            "Référence",
            "Type",
            "Partenaire",
            "Facture",
            "Catégorie",
            "Date",
            "Devise",
            "Montant devise",
            "Montant société",
            "État",
        ]
        for col, title in enumerate(headers):
            sheet.write(0, col, title, header)
        row = 1
        for rec in payments:
            sheet.write(row, 0, rec.name or "")
            sheet.write(row, 1, rec.payment_type or "")
            sheet.write(row, 2, rec.partner_id.display_name or "")
            sheet.write(row, 3, rec.invoice_id.name or rec.invoice_id.ref or "")
            sheet.write(row, 4, rec.category_id.name or "")
            sheet.write(row, 5, str(rec.payment_date or ""))
            sheet.write(row, 6, rec.currency_id.name or "")
            sheet.write(row, 7, rec.amount_currency or 0.0)
            sheet.write(row, 8, rec.amount or 0.0)
            sheet.write(row, 9, rec.state or "")
            row += 1
