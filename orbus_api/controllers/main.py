import json
import requests
from datetime import datetime
from odoo import http
from odoo.http import request


class OrbusAPI(http.Controller):

    # ===============================
    # TOKEN
    # ===============================
    def _check_token(self):
        auth = request.httprequest.headers.get('Authorization')
        token = request.env['ir.config_parameter'].sudo().get_param('api.bearer.token')
        return auth == f"Bearer {token}"

    # ===============================
    # EMPLOYEE MAPPING
    # ===============================
    def _get_employee(self, matricule):
        return request.env['hr.employee'].sudo().search([
            ('registration_number', '=', matricule)
        ], limit=1)

    # ===============================
    # PARSE PERIODE
    # ===============================
    def _get_dates(self, periode):
        date_from = datetime.strptime(periode, "%m-%Y").replace(day=1)
        if date_from.month == 12:
            date_to = date_from.replace(year=date_from.year + 1, month=1, day=1)
        else:
            date_to = date_from.replace(month=date_from.month + 1, day=1)
        return date_from, date_to

    # ===============================
    # 1. DISPONIBILITÉ BULLETINS
    # ===============================
    @http.route('/orbus/IsSalaireDisponible/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def is_salaire_disponible(self, periode):

        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        date_from, date_to = self._get_dates(periode)

        count = request.env['hr.payslip'].sudo().search_count([
            ('date_from', '>=', date_from),
            ('date_to', '<', date_to),
            ('state', '=', 'done')
        ])

        return request.make_response(
            "true" if count > 0 else "false",
            headers=[('Content-Type', 'text/plain')]
        )

    # ===============================
    # 2. DONNÉES SALAIRES
    # ===============================
    @http.route('/orbus/GetSalaires/data/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_salaires(self, periode, **kwargs):

        if not self._check_token():
            return request.make_response(json.dumps({"error": "Unauthorized"}), status=401)

        matricule = kwargs.get('matricule')

        date_from, date_to = self._get_dates(periode)

        domain = [
            ('date_from', '>=', date_from),
            ('date_to', '<', date_to),
            ('state', '=', 'done')
        ]

        if matricule:
            emp = self._get_employee(matricule)
            if not emp:
                return request.make_response(json.dumps([]))
            domain.append(('employee_id', '=', emp.id))

        slips = request.env['hr.payslip'].sudo().search(domain)

        result = []

        for slip in slips:

            lines = {l.code: l.total for l in slip.line_ids}

            result.append({
                "matricule": slip.employee_id.registration_number,
                "periode": periode,
                "date_salaire": slip.date_to.strftime('%d/%m/%Y'),
                "salaire_brut": lines.get('GROSS', 0),
                "impot": lines.get('CSAL1', 0),  # adapter selon config
                "salaire_net": lines.get('NET', 0)
            })

        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    # ===============================
    # 3. LISTE BULLETINS
    # ===============================
    @http.route('/orbus/files/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def list_bulletins(self, periode):

        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        date_from, date_to = self._get_dates(periode)

        slips = request.env['hr.payslip'].sudo().search([
            ('date_from', '>=', date_from),
            ('date_to', '<', date_to),
            ('state', '=', 'done')
        ])

        result = []

        for slip in slips:
            result.append({
                "matricule": slip.employee_id.registration_number,
                "url": f"/orbus/files/{periode}/{slip.employee_id.registration_number}"
            })

        return request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )

    # ===============================
    # 4. PDF BULLETIN RÉEL
    # ===============================
    @http.route('/orbus/files/<string:periode>/<path:matricule>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_bulletin(self, periode, matricule):

        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        # 1. Recherche employé
        employee = request.env['hr.employee'].sudo().search([
            ('registration_number', '=', matricule)
        ], limit=1)

        if not employee:
            return request.make_response("Employé introuvable", status=404)

        # 2. Convertir période MM-YYYY → dates
        try:
            month, year = periode.split('-')
            date_from = f"{year}-{month}-01"
            date_to = f"{year}-{month}-31"
        except:
            return request.make_response("Format période invalide (MM-YYYY attendu)", status=400)

        # 3. Recherche bulletin CORRECTE
        payslip = request.env['hr.payslip'].sudo().search([
            ('employee_id', '=', employee.id),
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', '=', 'done')
        ], limit=1)

        if not payslip:
            return request.make_response("Bulletin introuvable", status=404)

        # 4. Génération PDF réel
        pdf, _ = request.env['ir.actions.report']._render_qweb_pdf(
            'hr_payroll.action_report_payslip',
            [payslip.id]
        )

        return request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="bulletin_{matricule}.pdf"')
            ]
        )

    # ===============================
    # 5. ENCOURS CONGÉS
    # ===============================
    @http.route('/orbus/getEncours/<string:year>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_encours(self, year):

        if not self._check_token():
            return request.make_response(json.dumps({"error": "Unauthorized"}), status=401)

        token = request.env['ir.config_parameter'].sudo().get_param('orbus.api.token')

        url = f"https://gesperformance.gainde2000.sn/interface/getEncours/{year}"

        try:
            res = requests.get(url, headers={"Authorization": f"Bearer {token}"})

            data = res.json()
            result = []

            for item in data:
                emp = self._get_employee(item.get("matricule"))

                result.append({
                    "matricule": item.get("matricule"),
                    "employee_name": emp.name if emp else "Non trouvé",
                    "solde": item.get("solde")
                })

            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        except Exception as e:
            return request.make_response(json.dumps({"error": str(e)}), status=500)


