# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request

class AuditGaindeDashboard(http.Controller):

    @http.route('/audit_gainde/dashboard_data', type='json', auth='user')
    def dashboard_data(self):
        Mission = request.env['audit_gainde.mission'].sudo()
        Risk = request.env['audit_gainde.risk'].sudo()

        # ==== KPIs missions ====
        total_missions = Mission.search_count([])
        closed_missions = Mission.search_count([('state','=','closed')])
        late_missions = Mission.search_count([('is_late','=',True)])
        avg_completion = sum(Mission.mapped('completion_rate')) / total_missions if total_missions else 0

        # ==== KPIs risques ====
        total_risks = Risk.search_count([])
        critical_risks = Risk.search_count([('level', '=', 'critical')])
        risks_with_mission = Risk.search_count([('mission_ids', '!=', False)])
        risks_without_control = Risk.search_count([('control_ids', '=', False)])

        # ==== Top 5 risques ====
        top_risks = sorted(
            [{'id': r.id, 'name': f"[{r.code}] {r.name}", 'count': len(r.mission_ids)} for r in Risk.search([])],
            key=lambda x: x['count'], reverse=True
        )[:5]

        # ==== Répartition risques par niveau ====
        level_data = []
        for level, label in Risk._fields['level'].selection:
            count = Risk.search_count([('level', '=', level)])
            level_data.append({'level': label, 'count': count})

        # ==== Répartition risques par domaine ====
        domain_data = []
        domains = Risk.read_group([], ['domain'], ['domain'])
        for d in domains:
            domain_data.append({'domain': d['domain'], 'count': d['domain_count']})

        return {
            'mission_kpis': {
                'total': total_missions,
                'closed': closed_missions,
                'late': late_missions,
                'avg_completion': avg_completion
            },
            'risk_kpis': {
                'total': total_risks,
                'critical': critical_risks,
                'with_mission': risks_with_mission,
                'without_control': risks_without_control
            },
            'top_risks': top_risks,
            'levels': level_data,
            'domains': domain_data
        }