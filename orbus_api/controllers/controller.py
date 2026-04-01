
        

import requests
from odoo import http
from odoo.http import request

class OrbusAPI(http.Controller):

    def _check_token(self):
        auth = request.httprequest.headers.get('Authorization')
        token_config = request.env['ir.config_parameter'].sudo().get_param('api.bearer.token')
        return auth == f"Bearer {token_config}"

    def _get_employee_by_matricule(self, matricule):
        employee = request.env['hr.employee'].sudo().search([('barcode', '=', matricule)], limit=1)
        return employee

    # ===============================
    # Endpoint 1 : Disponibilité salaires
    # ===============================
    @http.route('/orbus/IsSalaireDisponible/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def is_salaire_disponible(self, periode):
        if not self._check_token():
            return request.make_response("Unauthorized", status=401)
        return request.make_response("true", headers=[('Content-Type', 'text/plain')])

    # ===============================
    # Endpoint 2 : Récupération données salaires
    # ===============================
    @http.route('/orbus/GetSalaires/data/<string:periode>', type='json', auth='public', methods=['GET'], csrf=False)
    def get_salaires(self, periode):
        if not self._check_token():
            return {"error": "Unauthorized"}

        return [
            {
                "matricule": "EMP001",
                "periode": periode,
                "date_salaire": "31/03/2026",
                "salaire_brut": 500000,
                "impot": 50000,
                "salaire_net": 450000
            }
        ]

    # ===============================
    # Endpoint 3 : Récupération PDF bulletin
    # ===============================
    @http.route('/orbus/files/<string:periode>/<string:matricule>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_bulletin(self, periode, matricule):
        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        pdf_content = b"%PDF-1.4 Dummy PDF content"
        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="bulletin_{matricule}.pdf"')
            ]
        )

    # ===============================
    # Endpoint 4 : Encours de congés avec mapping automatique employés
    # ===============================
    @http.route('/orbus/getEncours/<string:year>', type='json', auth='public', methods=['GET'], csrf=False)
    def get_encours_conges(self, year):
        if not self._check_token():
            return {"error": "Unauthorized"}

        # URL externe pour les congés
        url = f"https://gesperformance.gainde2000.sn/interface/getEncours/{year}"
        headers = {
            "Authorization": "Bearer odoo_orbus_@!token"  # Même token que Postman pour tests
        }

        try:
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                return {
                    "error": "Erreur API externe",
                    "status": response.status_code,
                    "message": response.text
                }

            data = response.json()
            result = []

            for item in data:
                matricule = item.get("matricule")
                employee = self._get_employee_by_matricule(matricule)
                result.append({
                    "matricule": matricule,
                    "employee_id": employee.id if employee else False,
                    "employee_name": employee.name if employee else "Non trouvé",
                    "nom_droit": item.get("nom_droit"),
                    "code": item.get("code"),
                    "nombre_autorise": item.get("nombre_autorise"),
                    "nombre_pris": item.get("nombre_pris"),
                    "solde": item.get("solde")
                })

            return result

        except Exception as e:
            return {"error": "Exception", "message": str(e)}
        


import json
import requests
from odoo import http
from odoo.http import request


class OrbusAPI(http.Controller):

    # ===============================
    # Sécurité TOKEN
    # ===============================
    def _check_token(self):
        auth = request.httprequest.headers.get('Authorization')
        token_config = request.env['ir.config_parameter'].sudo().get_param('api.bearer.token')
        return auth == f"Bearer {token_config}"

    # ===============================
    # Mapping employé
    # ===============================
    def _get_employee_by_matricule(self, matricule):
        return request.env['hr.employee'].sudo().search([
            ('barcode', '=', matricule)
        ], limit=1)

    # ===============================
    # 1. Disponibilité salaires
    # ===============================
    @http.route('/orbus/IsSalaireDisponible/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def is_salaire_disponible(self, periode):

        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        return request.make_response("true", headers=[('Content-Type', 'text/plain')])

    # ===============================
    # 2. Salaires (FIX JSON)
    # ===============================
    @http.route('/orbus/GetSalaires/data/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_salaires(self, periode):

        if not self._check_token():
            return request.make_response(json.dumps({"error": "Unauthorized"}), status=401)

        data = [
            {
                "matricule": "EMP001",
                "periode": periode,
                "date_salaire": "31/03/2026",
                "salaire_brut": 500000,
                "impot": 50000,
                "salaire_net": 450000
            }
        ]

        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')]
        )

    # ===============================
    # 3. Liste bulletins
    # ===============================
    @http.route('/orbus/files/<string:periode>', type='http', auth='public', methods=['GET'], csrf=False)
    def list_bulletins(self, periode):

        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        files = [
            {"matricule": "EMP001", "file": f"/orbus/files/{periode}/EMP001"}
        ]

        return request.make_response(
            json.dumps(files),
            headers=[('Content-Type', 'application/json')]
        )

    # ===============================
    # 4. Bulletin PDF
    # ===============================
    @http.route('/orbus/files/<string:periode>/<string:matricule>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_bulletin(self, periode, matricule):

        if not self._check_token():
            return request.make_response("Unauthorized", status=401)

        pdf_content = b"%PDF-1.4 Dummy PDF content"

        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="bulletin_{matricule}.pdf"')
            ]
        )

    # ===============================
    # 5. Encours congés
    # ===============================
    @http.route('/orbus/getEncours/<string:year>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_encours_conges(self, year):

        if not self._check_token():
            return request.make_response(json.dumps({"error": "Unauthorized"}), status=401)

        external_token = request.env['ir.config_parameter'].sudo().get_param('orbus.api.token')

        url = f"https://gesperformance.gainde2000.sn/interface/getEncours/{year}"

        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {external_token}"},
                timeout=20
            )

            if response.status_code != 200:
                return request.make_response(json.dumps({
                    "error": "Erreur API externe",
                    "status": response.status_code
                }), status=500)

            data = response.json()
            result = []

            for item in data:
                matricule = item.get("matricule")
                employee = self._get_employee_by_matricule(matricule)

                result.append({
                    "matricule": matricule,
                    "employee_id": employee.id if employee else False,
                    "employee_name": employee.name if employee else "Non trouvé",
                    "nom_droit": item.get("nom_droit"),
                    "code": item.get("code"),
                    "nombre_autorise": item.get("nombre_autorise"),
                    "nombre_pris": item.get("nombre_pris"),
                    "solde": item.get("solde")
                })

            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )

        except Exception as e:
            return request.make_response(
                json.dumps({"error": str(e)}),
                status=500
            )