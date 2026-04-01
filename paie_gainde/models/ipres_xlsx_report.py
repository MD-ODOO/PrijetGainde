# -*- coding: utf-8 -*-

from odoo import models, fields, api
import base64
import io
import csv
from openpyxl import Workbook
from datetime import date


class IPRESExportWizard(models.TransientModel):
    _name = "ipres.export.wizard"
    _description = "Export IPRES Excel / CSV"

    company_id = fields.Many2one(
        'res.company',
        string="Entreprise",
        default=lambda self: self.env.company,
        required=True
    )
    month = fields.Selection(
        [(str(i), str(i)) for i in range(1, 13)],
        string="Mois",
        required=True
    )
    year = fields.Integer(
        string="AnnÃ©e",
        default=lambda self: date.today().year,
        required=True
    )
    export_type = fields.Selection(
        [('xlsx', 'Excel'), ('csv', 'CSV')],
        default='xlsx',
        string="Format"
    )

    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    # ==========================================================
    # í ½í´¹ DONNÃ‰ES IPRES PAR BULLETIN
    # ==========================================================
    def _get_ipres_data(self, slip):
        categories = slip._get_categories_dict()

        brut = categories.get('BTOTAL', 0.0)
        heures = sum(
            slip.worked_days_line_ids.mapped('number_of_hours')
        )

        cadre = "Oui" if slip.contract_id.regime_type and \
            slip.contract_id.regime_type.lower().find("cadre") >= 0 else "Non"

        emp = slip.employee_id

        return {
            'nss': emp.identification_id or '',
            'nom': emp.name or '',
            'prenom': emp.first_name or '',
            'type_piece': emp.identification_type or '',
            'num_piece': emp.identification_id or '',
            'contrat': slip.contract_id.contract_type_id.name or '',
            'brut': brut,
            'heures': heures,
            'cadre': cadre,
        }

    # ==========================================================
    # í ½í´¹ ACTION EXPORT
    # ==========================================================
    def action_export(self):
        slips = self.env['hr.payslip'].search([
            ('date_from', '>=', f'{self.year}-{self.month}-01'),
            ('date_to', '<=', f'{self.year}-{self.month}-31'),
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
        ])

        rows = []
        total_brut = total_heures = 0.0
        total_cadres = total_non_cadres = 0

        for slip in slips:
            line = self._get_ipres_data(slip)
            rows.append(line)

            total_brut += line['brut']
            total_heures += line['heures']

            if line['cadre'] == 'Oui':
                total_cadres += 1
            else:
                total_non_cadres += 1

        if self.export_type == 'xlsx':
            return self._export_xlsx(rows, total_brut, total_heures,
                                     total_cadres, total_non_cadres)
        else:
            return self._export_csv(rows, total_brut, total_heures,
                                    total_cadres, total_non_cadres)

    # ==========================================================
    # í ½í´¹ EXPORT EXCEL
    # ==========================================================
    def _export_xlsx(self, rows, total_brut, total_heures,
                     total_cadres, total_non_cadres):

        wb = Workbook()
        ws = wb.active
        ws.title = "IPRES"

        ws.append([
            "NSS", "Nom", "PrÃ©nom", "Type piÃ¨ce", "NÂ° piÃ¨ce",
            "Type contrat", "Salaire brut assujetti",
            "Heures", "Cadre"
        ])

        for r in rows:
            ws.append([
                r['nss'], r['nom'], r['prenom'], r['type_piece'],
                r['num_piece'], r['contrat'], r['brut'],
                r['heures'], r['cadre']
            ])

        ws.append([])
        ws.append(["TOTAL BRUT ASSUJETTI", total_brut])
        ws.append(["TOTAL HEURES", total_heures])
        ws.append(["TOTAL CADRES", total_cadres])
        ws.append(["TOTAL NON CADRES", total_non_cadres])

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        self.file_data = base64.b64encode(buffer.read())
        self.file_name = f"IPRES_{self.company_id.name}_{self.month}_{self.year}.xlsx"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    # ==========================================================
    # í ½í´¹ EXPORT CSV
    # ==========================================================
    def _export_csv(self, rows, total_brut, total_heures,
                    total_cadres, total_non_cadres):

        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')

        writer.writerow([
            "NSS", "Nom", "PrÃ©nom", "Type piÃ¨ce", "NÂ° piÃ¨ce",
            "Type contrat", "Salaire brut assujetti",
            "Heures", "Cadre"
        ])

        for r in rows:
            writer.writerow([
                r['nss'], r['nom'], r['prenom'], r['type_piece'],
                r['num_piece'], r['contrat'], r['brut'],
                r['heures'], r['cadre']
            ])

        writer.writerow([])
        writer.writerow(["TOTAL BRUT ASSUJETTI", total_brut])
        writer.writerow(["TOTAL HEURES", total_heures])
        writer.writerow(["TOTAL CADRES", total_cadres])
        writer.writerow(["TOTAL NON CADRES", total_non_cadres])

        self.file_data = base64.b64encode(buffer.getvalue().encode())
        self.file_name = f"IPRES_{self.company_id.name}_{self.month}_{self.year}.csv"

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }