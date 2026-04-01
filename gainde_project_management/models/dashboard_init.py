import json
import base64
from odoo import api, SUPERUSER_ID


def post_init_gainde_dashboard(*args, **kwargs):
    """ Initialisation du dashboard spreadsheet """
    if len(args) == 1 and isinstance(args[0], api.Environment):
        env = args[0]
    elif len(args) >= 1:
        cr = args[0]
        env = api.Environment(cr, SUPERUSER_ID, {})
    else:
        return

    group_project = env.ref(
        'spreadsheet_dashboard.spreadsheet_dashboard_group_project',
        raise_if_not_found=False)
    if not group_project:
        group_project = env['spreadsheet.dashboard.group'].create(
            {'name': 'Projets Group', 'sequence': 10})

    dashboard_data = {
        "version": 16,
        "sheets": [{
            "id": "sheet_gainde",
            "name": "Analyse Gainde",
            "cells": {
                "A1": {"content": "Budget Total"},
                "B1": {"content": '=ODOO.PIVOT.VALUE("1", "budget_total")'},
                "A2": {"content": "Coûts Réalisés"},
                "B2": {"content": '=ODOO.PIVOT.VALUE("1", "realized_costs")'},
                "A3": {"content": "Coûts Engagés"},
                "B3": {"content": '=ODOO.PIVOT.VALUE("1", "engaged_costs")'},
                "A4": {"content": "Budget Restant"},
                "B4": {"content": "=B1-B2-B3"}
            }
        }],
        "pivots": {
            "1": {
                "model": "project.project",
                "measures": [
                    {"field": "budget_total"},
                    {"field": "realized_costs"},
                    {"field": "engaged_costs"}
                ],
                "name": "Données Gainde"
            }
        }
    }

    data_encoded = base64.b64encode(json.dumps(dashboard_data).encode('utf-8'))

    dashboard = env['spreadsheet.dashboard'].search(
        [('name', '=', 'Dashboard Gainde')], limit=1)
    vals = {
        'name': 'Dashboard Gainde',
        'dashboard_group_id': group_project.id,
        'spreadsheet_data': data_encoded,
        'is_published': True,
    }

    if dashboard:
        dashboard.write(vals)
    else:
        env['spreadsheet.dashboard'].create(vals)
