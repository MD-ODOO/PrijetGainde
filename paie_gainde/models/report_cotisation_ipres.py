# -*- coding: utf-8 -*-
from odoo import models,api,fields
from datetime import date, timedelta, datetime
from collections import defaultdict
from odoo.exceptions import UserError
from babel.dates import format_date



class IpresXlsxReport(models.AbstractModel):
    _name = 'report.paie_gainde.report_ipres_xlsx' 
    _inherit = 'report.report_xlsx.abstract'
    _description = u'reporting'
    def generate_xlsx_report(self, workbook, data, wizard):

        header_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'align': 'center', 'bg_color': '#D3D3D3'
        })
        cell_fmt = workbook.add_format({'border': 1})
        title_fmt = workbook.add_format({'bold': True, 'font_size': 14})

        sheet = workbook.add_worksheet('IPRES')

        # ===============================
        # 1. EN-T�TE EMPLOYEUR
        # ===============================
        company = self.env.company
        sheet.write('A2', 'NOM EMPLOYEUR :', title_fmt)
        sheet.write('A3', company.name)

        sheet.write('B2', 'ANNEE :', title_fmt)
        sheet.write('B3', wizard.date_to.year)
        

        mois_fr = {
            1: 'Janvier', 2: 'Fevrier', 3: 'Mars', 4: 'Avril',
            5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Aout',
            9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Decembre'
        }
        sheet.write('C2', 'MOIS :', title_fmt)
        sheet.write('C3', mois_fr[wizard.date_to.month])

        # ===============================
        # 2. EN-T�TES TABLEAU IPRES
        # ===============================
        headers = [
            'Num Assurance Sociale',
            'Nom',
            'Prenom',
            'Type Piece',
            'Numero de Piece',
            'Type Contrat',
            'Salaire Brut Assujetti',
            'Temps Presence (H)',
            'Cadre (Oui/Non)'
        ]

        header_row = 5
        for col, title in enumerate(headers):
            sheet.write(header_row, col, title, header_fmt)

        # ===============================
        # 3. COLLECTE DES DONN�ES
        # ===============================
        payslips = self.env['hr.payslip'].search([
            ('state', '=', 'paid'),
            ('date_from', '>=', wizard.date_from),
            ('date_to', '<=', wizard.date_to),
        ])

        employees_data = {}

        for slip in payslips:
            emp = slip.employee_id

            if emp.id not in employees_data:
                employees_data[emp.id] = {
                    'employee': emp,
                    'num_as': emp.ssnid or '',
                    'nom': emp.name.split(' ')[-1] if emp.name else '',
                    'prenom': ' '.join(emp.name.split(' ')[:-1]) if emp.name else '',
                    'type_piece': 'Passeport' if emp.passport_id else 'CNI',
                    'num_piece': emp.passport_id or emp.identification_id or '',
                    'brut_ipres': 0.0,
                    'hours': 0.0,
                    'is_cadre': 'Non',
                }

            # Brut IPRES (TPRES)
            for line in slip.line_ids:
                if line.code == 'GROSS':
                    employees_data[emp.id]['brut_ipres'] += line.total

            # Temps de pr�sence
            total_hours = 0.0

            for wd in slip.worked_days_line_ids:
               total_hours += wd.number_of_hours

            employees_data[emp.id]['hours'] = min(total_hours, 173.33)

            # Cadre
            if slip.contract_id and slip.contract_id.regime_type == 'cadre':
                employees_data[emp.id]['is_cadre'] = 'Oui'

        # ===============================
        # 4. REMPLISSAGE EXCEL
        # ===============================
        row = 6
        for data_emp in employees_data.values():
            emp = data_emp['employee']

            contract = self.env['hr.contract'].search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'open')
            ], limit=1)

            sheet.write(row, 0, data_emp['num_as'], cell_fmt)
            sheet.write(row, 1, data_emp['nom'], cell_fmt)
            sheet.write(row, 2, data_emp['prenom'], cell_fmt)
            sheet.write(row, 3, data_emp['type_piece'], cell_fmt)
            sheet.write(row, 4, data_emp['num_piece'], cell_fmt)
            sheet.write(row, 5, contract.contract_type_id.name if contract else '', cell_fmt)
            sheet.write(row, 6, data_emp['brut_ipres'], cell_fmt)
            sheet.write(row, 7, data_emp['hours'], cell_fmt)
            sheet.write(row, 8, data_emp['is_cadre'], cell_fmt)

            row += 1

        sheet.set_column('A:I', 22)
        







class ReportCotisationIPRES(models.AbstractModel):
    _name = 'report.paie_gainde.report_ipres_template'
    _description = 'Rapport IPRES PDF - Final Stable Odoo 18'

    @api.model
    def _get_report_values(self, docids, data=None):

        # ================= S�CURIT� =================
        data = data or {}

        date_from = data.get('date_from')
        date_to = data.get('date_to')

        if not date_from or not date_to:
            raise UserError(
                "Veuillez definir une periode valide (date de debut et date de fin)."
            )

        # ================= WIZARD =================
        wizard = self.env['cerco.payslip.lines.cotisation.ipres'].browse(docids)
        company = wizard.company_id if wizard and hasattr(wizard, 'company_id') else self.env.company

        # ================= BULLETINS =================
        slips = self.env['hr.payslip'].search([
            ('state', 'in', [ 'done','paid']),
            ('date_from', '<=', date_to),
            ('date_to', '>=', date_from),
            ('company_id', '=', company.id),
        ], order='employee_id')

        if not slips:
            raise UserError(
                "Aucun bulletin valide pour cette periode.\n"
                "Verifiez que les bulletins sont valides ou payes."
            )

        # ================= DONN�ES =================
        rows = []
        totals = defaultdict(float)
        index = 1

        for slip in slips:
            line_map = {l.code: l.total for l in slip.line_ids if l.code}

            brut = line_map.get('GROSS', 0.0)

            # --- Bases IPRES ---
            rg_base = line_map.get('CASH3', 0.0)
            rc_base = line_map.get('CASH4', 0.0)
            rc_con_base = line_map.get('CASH6', 0.0)
            rg_con_base = line_map.get('ALCON', 0.0)

            # --- Cotisations ---
            rg_emp = round(rg_base * 0.056, 1)
            rg_pat = round(rg_base * 0.084, 1)
            rg_con_emp = round(rg_con_base * 0.056, 1)
            rg_con_pat = round(rg_con_base * 0.084, 1)

            rc_emp = round(rc_base * 0.024, 1)
            rc_pat = round(rc_base * 0.036, 1)
            rc_con_emp = round(rc_con_base * 0.024, 1)
            rc_con_pat = round(rc_con_base * 0.036, 1)

            total_line = round(rg_emp + rg_pat + rc_emp + rc_pat+rg_con_emp + rg_con_pat + rc_con_emp + rc_con_pat, 1)

            row = {
                'num': index,
                'matricule': slip.employee_id.registration_number or '',
                'nom': slip.employee_id.name or '',

                'brut': round(brut, 1),

                'rg_base': round(rg_base, 1),
                'rg_emp': rg_emp,
                'rg_pat': rg_pat,
                
                'rg_con_base': round(rg_con_base, 1),
                'rg_con_emp': rg_con_emp,
                'rg_con_pat': rg_con_pat,

                'rc_base': round(rc_base, 1),
                'rc_emp': rc_emp,
                'rc_pat': rc_pat,
                
                'rc_con_base': round(rc_con_base, 1),
                'rc_con_emp': rc_con_emp,
                'rc_con_pat': rc_con_pat,

                'total': total_line,
            }

            rows.append(row)

            # --- Totaux cumul�s (toutes pages) ---
            totals['brut'] += row['brut']

            totals['rg_base'] += row['rg_base']
            totals['rg_emp'] += rg_emp
            totals['rg_pat'] += rg_pat
            
            totals['rg_con_base'] += row['rg_con_base']
            totals['rg_con_emp'] += rg_con_emp
            totals['rg_con_pat'] += rg_con_pat

            totals['rc_base'] += row['rc_base']
            totals['rc_emp'] += rc_emp
            totals['rc_pat'] += rc_pat
            
            totals['rc_con_base'] += row['rc_con_base']
            totals['rc_con_emp'] += rc_con_emp
            totals['rc_con_pat'] += rc_con_pat

            totals['total'] += total_line

            index += 1

        # ================= ARRONDIS FINAUX =================
        for key in totals:
            totals[key] = round(totals[key], 1)

        # ================= CONTEXTE QWEB =================
        return {
            'doc_ids': docids,
            'doc_model': 'cerco.payslip.lines.cotisation.ipres',
            'docs': wizard,

            'company': company,

            'rows': rows,
            'totals': totals,

            'date_from': date_from,
            'date_to': date_to,

            'print_date': fields.Datetime.now().strftime('%d/%m/%Y %H:%M'),
        }
        


class ReportLivrePaie(models.AbstractModel):
    _name = "report.paie_gainde.livre_paie_template"
    _description = "Livre de paie PDF"

    @api.model
    def _get_report_values(self, docids, data=None):
        wizard = self.env["cerco.payslip.lines.cotisation.ipres"].browse(docids)

        slips = self.env["hr.payslip"].search([
            ("date_from", ">=", wizard.date_from),
            ("date_to", "<=", wizard.date_to),
            ("state", 'in', ['done', 'paid']),
        ])

        employees = {}

        for slip in slips:
            emp = slip.employee_id
            employees.setdefault(emp, defaultdict(float))

            for line in slip.line_ids:
                employees[emp][(line.code, line.name)] += line.amount
                
        company = self.env.company   # ? TR�S IMPORTANT

        return {
            "employees": employees,
            "date_from": wizard.date_from,
            "date_to": wizard.date_to,
            "year": wizard.date_to.year,
            "company": company,        # ? inject� dans QWeb
        }







class ReportRASDGID(models.AbstractModel):
    _name = 'report.paie_gainde.report_ras_template'
    _description = 'Declaration RAS DGID Salaires'

    @api.model
    def _get_report_values(self, docids, data=None):

        data = data or {}
        company = self.env.company

        # =========================
        # DATES (SECURITE STR -> DATE)
        # =========================
        date_from = data.get('date_from')
        date_to = data.get('date_to')

        if isinstance(date_from, str):
            date_from = fields.Date.from_string(date_from)

        if isinstance(date_to, str):
            date_to = fields.Date.from_string(date_to)

        # =========================
        # BULLETINS
        # =========================
        slips = self.env['hr.payslip'].search([
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['done', 'paid']),
        ])

        employees = slips.mapped('employee_id')

        # =========================
        # OUTILS
        # =========================
        def sum_line(code):
            return sum(
                slips.mapped('line_ids')
                .filtered(lambda l: l.code == code)
                .mapped('amount')
            )

        def sum_gross_by_country(is_sn=True):
            return sum(
                slips.mapped('line_ids')
                .filtered(
                    lambda l: l.code == 'GROSS' and (
                        (l.slip_id.employee_id.country_id
                         and l.slip_id.employee_id.country_id.code == 'SN')
                        if is_sn
                        else (
                            not l.slip_id.employee_id.country_id
                            or l.slip_id.employee_id.country_id.code != 'SN'
                        )
                    )
                )
                .mapped('amount')
            )

        # =========================
        # EFFECTIFS
        # =========================
        effectif_sn = len(employees.filtered(
            lambda e: e.country_id and e.country_id.code == 'SN'
        ))
        effectif_ex = len(employees.filtered(
            lambda e: not e.country_id or e.country_id.code != 'SN'
        ))
        effectif_total = effectif_sn + effectif_ex

        # =========================
        # SALAIRES
        # =========================
        salaires_sn = sum_gross_by_country(is_sn=True)
        salaires_ex = sum_gross_by_country(is_sn=False)
        masse_salariale = sum_line('GROSS')

        # =========================
        # IMPOTS
        # =========================
        ir_retenu = sum_line('CSAL1')
        trimf = sum_line('CSAL2')
        cfce = sum_line('CPAT5')
        gta = sum_line('GTA')

        montant_net_ir = ir_retenu - gta
        ir_du = montant_net_ir
        montant_paye = ir_du + trimf + cfce

        # =========================
        # FORMAT DATES FR
        # =========================
        periode_imposition = (
            format_date(date_to, format='MMMM yyyy', locale='fr')
            if date_to else ''
        )

        date_limite_depot = (
            format_date(date_to, format='dd/MM/yyyy', locale='fr')
            if date_to else ''
        )

        date_limite_paiement = (
            format_date(date_to + timedelta(days=15), format='dd/MM/yyyy', locale='fr')
            if date_to else ''
        )

        impression_date = format_date(
            fields.Date.context_today(self),
            format='dd MMMM yyyy',
            locale='fr'
        )

        return {
            # ENTREPRISE
            'company_name': company.name,
            'ninea': company.vat or '',
            'centre_fiscal': company.partner_id.contact_address or '',
            'adresse_correspondance': company.partner_id.contact_address or '',

            # FISCAL
            'nature_impot': 'RAS SALAIRES CONSOLIDEES',
            'objet_imposable': 'Salaires',

            # PERIODE
            'date_from': date_from,
            'date_to': date_to,
            'periode_imposition': periode_imposition,
            'date_limite_depot': date_limite_depot,
            'date_limite_paiement': date_limite_paiement,

            # EFFECTIFS
            'effectif_sn': effectif_sn,
            'effectif_ex': effectif_ex,
            'effectif_total': effectif_total,

            # SALAIRES
            'salaires_sn': salaires_sn,
            'salaires_ex': salaires_ex,
            'masse_salariale': masse_salariale,

            # IMPOTS
            'ir_retenu': ir_retenu,
            'gta': gta,
            'montant_net_ir': montant_net_ir,
            'ir_du': ir_du,
            'trimf': trimf,
            'cfce': cfce,
            'montant_paye': montant_paye,

            # PIED DE PAGE
            'impression_date': impression_date,
            'numero_document': f"RAS-{date_to.strftime('%Y%m')}" if date_to else '',
            'numero_compte': company.bank_ids[:1].acc_number if company.bank_ids else '',
            'centre_fiscal_caissier': 'CME',
            'page': 1,
            'page_total': 1,
        }









class ReportDeclarationCSS(models.AbstractModel):
    _name = 'report.paie_gainde.report_css_declaration'
    _description = 'Declaration mensuelle de cotisations CSS'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        company = self.env.company

        date_from = data.get('date_from')
        periode = ''
        if isinstance(date_from, (date, datetime)):
            periode = format_date(
                date_from,
                format='MMMM yyyy',
                locale='fr'
            ).capitalize()
        
        date_decl = data.get('date_declaration') or date_from
        date_declaration_str = ''
        if isinstance(date_decl, (date, datetime)):
            date_declaration_str = format_date(
                date_decl,
                format='d MMMM yyyy',
                locale='fr'
            ).capitalize()
        
        date_to = data.get('date_to')

        slips = self.env['hr.payslip'].search([
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['done', 'paid']),
        ])

        # ================= INITIALISATION =================
        eff_perm_ge_63 = eff_perm_lt_63 = 0
        eff_cdd_ge_63 = eff_cdd_lt_63 = 0
        eff_journalier = eff_apprenti = 0

        sal_perm_ge_63 = sal_perm_lt_63 = 0.0
        sal_cdd_ge_63 = sal_cdd_lt_63 = 0.0
        sal_journalier = alloc_apprenti = 0.0

        total_salaires = 0.0

        # ================= PAR BULLETIN =================
        for slip in slips:
            contract = slip.contract_id
            if not contract or not contract.contract_type_id:
                continue

            ctype = (contract.contract_type_id.name or '')

            brut = sum(
                slip.line_ids.filtered(lambda l: l.code == 'GROSS').mapped('total')
            )
            total_salaires += brut

            if 'Permanent' in ctype or 'CDI' in ctype:
                if brut >= 63000:
                    eff_perm_ge_63 += 1
                    sal_perm_ge_63 += brut
                else:
                    eff_perm_lt_63 += 1
                    sal_perm_lt_63 += brut

            elif 'cdd' in ctype or 'temporaire' in ctype:
                if brut >= 63000:
                    eff_cdd_ge_63 += 1
                    sal_cdd_ge_63 += brut
                else:
                    eff_cdd_lt_63 += 1
                    sal_cdd_lt_63 += brut

            elif 'journalier' in ctype:
                eff_journalier += 1
                sal_journalier += brut

            elif 'apprenti' in ctype or 'stagiaire' in ctype:
                eff_apprenti += 1
                alloc_apprenti += brut

        # ================= TOTAUX =================
        # A+B+C+D+E
        base_pf = (
            sal_perm_ge_63
            + sal_perm_lt_63
            + sal_cdd_ge_63
            + sal_cdd_lt_63
            + sal_journalier
        )

        # A+B+C+D+E+F
        base_atmp = base_pf + alloc_apprenti

        # ================= TAUX CSS =================
        taux_pf = 0.07      # Prestations familiales 7%
        taux_atmp = 0.03    # Accidents du travail 3%

        cot_pf = base_pf * taux_pf
        cot_atmp = base_atmp * taux_atmp
        cot_total = cot_pf + cot_atmp

        # ================= DATE =================
        date_decl = data.get('date_declaration')
        date_declaration_str = (
            date_decl.strftime('%d/%m/%Y')
            if isinstance(date_decl, (date, datetime)) else ''
        )

        return {
            'company': self.env.company,
            'periode': data.get('periode', ''),
            'date_declaration_str': date_declaration_str,

            'effectif_global': len(slips),
            'total_salaires': total_salaires,

            # Effectifs / montants A � F
            'eff_perm_ge_63': eff_perm_ge_63, 'sal_perm_ge_63': sal_perm_ge_63,
            'eff_perm_lt_63': eff_perm_lt_63, 'sal_perm_lt_63': sal_perm_lt_63,
            'eff_cdd_ge_63': eff_cdd_ge_63,   'sal_cdd_ge_63': sal_cdd_ge_63,
            'eff_cdd_lt_63': eff_cdd_lt_63,   'sal_cdd_lt_63': sal_cdd_lt_63,
            'eff_journalier': eff_journalier, 'sal_journalier': sal_journalier,
            'eff_apprenti': eff_apprenti,     'alloc_apprenti': alloc_apprenti,

            # Bases
            'base_pf': base_pf,
            'base_atmp': base_atmp,

            # Cotisations
            'taux_pf': taux_pf * 100,
            'taux_atmp': taux_atmp * 100,
            'cot_pf': cot_pf,
            'cot_atmp': cot_atmp,
            'cot_total': cot_total,
            'company': company,
            'site': company.city or '',
            'periode': periode,
            'ninea': company.vat or '',
            'date_declaration_str': date_declaration_str,
            'type_employeur': 'Mensuel',
            'adresse_complete': ', '.join(filter(None, [
                company.street,
                company.street2,
                company.city,
                company.phone, ])),
        }

