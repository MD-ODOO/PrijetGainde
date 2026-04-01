# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AuditGaindeRisk(models.Model):
    """
    Modèle RISQUES identifiés dans une mission d'audit.

    HIÉRARCHIE : Plan → Mission → Risque
    CHAMPS : Code, description, domaine, niveau, contrôles existants
    """
    _name = 'audit_gainde.risk'
    _description = 'Risque d\'audit Gainde'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # ===========================================
    # IDENTIFICATION
    # ===========================================
    code = fields.Char(
        string='Code risque',
        required=True,
        default='New',
        copy=False,
        help="Code unique R001, R002..."
    )

    @api.constrains('code')
    def _check_code_unique(self):
        for record in self:
            duplicate = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(
                    f"La référence {record.code} existe déjà !"
                )

    domain = fields.Char(string='Domaine concerné', help='Domaine concerné', required=True)
    display_name = fields.Char(string='Nom affiché', compute='_compute_display_name')

    @api.depends('code', 'domain')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.domain or ''}"

    name = fields.Html(
        string='Description risque',
        required=True,
        translate=True
    )
    

    # ===========================================
    # RELATIONS
    # ===========================================
    

    # ===========================================
    # CARACTÉRISTIQUES RISQUE
    # ===========================================


    process = fields.Char(
        string='Processus lié',
        help="Processus lié impacté"
    )

    level = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('critical', 'Critique')
    ], string='Niveau risque', required=True, default='medium')

    probability = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Moyenne'),
        ('high', 'Élevée')
    ], string='Probabilité', required=True, default='medium')

    impact = fields.Selection([
        ('low', 'Faible'),
        ('medium', 'Modéré'),
        ('high', 'Fort'),
        ('critical', 'Critique')
    ], string='Impact', required=True, default='medium')

    # ===========================================
    # CONTRÔLES
    # ===========================================
    # Risque → Plusieurs contrôles
    control_ids = fields.One2many(
        'audit_gainde.control',
        'risk_id', 
        string='Contrôles existants')

    # ===========================================
    # STATUT
    # ===========================================

    # ===========================================
    # LIENS FUTURS
    # ===========================================
    finding_ids = fields.One2many(
        'audit_gainde.finding',
        'risk_id',
        string='Constats liés'
    )
    
    # ===========================================
    # Missions concernées
    # ===========================================
    
    mission_ids = fields.Many2many(
    'audit_gainde.mission',
    'audit_gainde_mission_risk_rel',  # MEME table !
    'risk_id',
    'mission_id',
    string='Missions concernées'
)

    # ===========================================
    # GÉNÉRATION CODE
    # ===========================================
    @api.model_create_multi
    def create(self, vals_list):
        """Génère code automatique R001, R002..."""
        for vals in vals_list:
            if vals.get('code', 'New') == 'New':
                # Compteur global (toutes missions confondues)
                count = self.search_count([]) + 1  # ← Simplifié
                vals['code'] = f"R{count:03d}"     # ← R001, R002...
        
        return super().create(vals_list)


    # ===========================================
    # NAVIGATION
    # ===========================================
    def action_view_findings(self):
        """Ouvre les constats liés"""
        return {
            'name': _('Constats'),
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.finding',
            'view_mode': 'list,form',
            'domain': [('risk_id', '=', self.id)]
        }


    # Surcharge write pour sécurité serveur
    def write(self, vals):
        for risk in self:
            # Si au moins une mission liée est clôturée
            if any(m.state == 'closed' for m in risk.mission_ids):
                # Autoriser uniquement la modification du champ 'state'
                allowed_fields = {'state'}
                if not set(vals.keys()).issubset(allowed_fields):
                    raise UserError(
                        "Impossible de modifier un risque lié à une mission clôturée."
                    )
        return super().write(vals)

    # Surcharge unlink pour sécurité serveur
    def unlink(self):
        for risk in self:
            if any(m.state == 'closed' for m in risk.mission_ids):
                raise UserError(
                    "Impossible de supprimer un risque lié à une mission clôturée."
                )
        return super().unlink()



    @api.model
    def get_dashboard_data(self):

        Risk = self.env['audit_gainde.risk']

        # KPI
        total_risks = Risk.search_count([])

        critical_risks = Risk.search_count([
            ('level', '=', 'critical')
        ])

        used_risks = Risk.search_count([
            ('mission_ids', '!=', False)
        ])

        no_control_risks = Risk.search_count([
            ('control_ids', '=', False)
        ])

        # TOP risques
        risks = Risk.search([])
        top_data = []

        for r in risks:
            top_data.append({
                "code": r.code,
                "count": len(r.mission_ids)
            })

        top_data = sorted(top_data, key=lambda x: x["count"], reverse=True)[:5]

        # Risques par niveau
        level_data = Risk.read_group(
            [],
            ['level'],
            ['level']
        )

        levels = []
        for l in level_data:
            levels.append({
                "level": l['level'],
                "count": l['level_count']
            })

        # Risques par domaine
        domain_data = Risk.read_group(
            [],
            ['domain'],
            ['domain']
        )

        domains = []
        for d in domain_data:
            domains.append({
                "domain": d['domain'],
                "count": d['domain_count']
            })

        return {
            "kpis": {
                "total": total_risks,
                "critical": critical_risks,
                "used": used_risks,
                "no_control": no_control_risks
            },
            "top_risks": top_data,
            "levels": levels,
            "domains": domains
        }

