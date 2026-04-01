# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AuditGaindeMission(models.Model):
    """
    Modèle MISSION D'AUDIT INDIVIDUELLE.

    CARACTÉRISTIQUES :
    - Liée à 1 plan d'audit gainde (hiérarchie)
    - Contient ses propres risques, constats, recommandations
    - Workflow : Planifiée → En cours → Revue → Clôturée
    """
    _name = 'audit_gainde.mission'
    _description = 'Mission d\'audit Gainde'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'display_name'

    # ===========================================
    # IDENTIFICATION
    # ===========================================
    reference = fields.Char(string='Référence', required=True, default='New', copy=False, readonly=True )
    name = fields.Char(string='Titre', required=True, help="Titre descriptif de la mission" )

    display_name = fields.Char(string='Nom affiché', compute='_compute_display_name')

    @api.depends('reference', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.reference}] {rec.name or ''}"
    
    period_start = fields.Date(string='Période début')
    period_end = fields.Date(string='Période fin')
    # ===========================================
    # RELATIONS HIÉRARCHIQUES
    # ===========================================
    plan_id = fields.Many2one(
        'audit_gainde.plan',
        string='Plan d\'audit',
        required=True,
        ondelete='cascade'
    )

    # ===========================================
    # MISSION PRINCIPALE
    # ===========================================
    domain = fields.Many2one(
    'audit_gainde.domain',
    string='Domaine audité',
    required=True)
    direction = fields.Char(string='Direction audité', help="Direction audité")

    objective = fields.Html(
        string='Objectif de la mission',
        required=True
    )


    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable audit',
        required=True,
        tracking=True,
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('audit_gainde.group_senior').ids)
        ],
    )

    team_ids = fields.Many2many(
        'res.users',
        'audit_mission_team_rel',
        'mission_id',
        'user_id',
        string='Équipe audit',
        domain=lambda self: [
        ('groups_id', 'in',
            (
                self.env.ref('audit_gainde.group_senior') |
                self.env.ref('audit_gainde.group_junior')
            ).ids
        )
    ],
    )
    
    responsible_domaine_audit_id = fields.Many2one(
        'res.users',
        string='Responsable du domaine audite',
        required=True,
        tracking=True
        
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        help="Société concernée par ce plan d'audit"
    )

    # ===========================================
    # WORKFLOW
    # ===========================================
    state = fields.Selection([
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('review', 'Revue'),
        ('closed', 'Clôturée')
    ], string='Statut', default='planned', tracking=True, group_expand='_group_expand_states')

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, val in self._fields['state'].selection]

    # ===========================================
    # SOUS-ÉLÉMENTS (One2many)
    # ===========================================
    risk_ids = fields.Many2many(
        'audit_gainde.risk',
        'audit_gainde_mission_risk_rel',  # Nom explicite
        'mission_id',
        'risk_id',
        string='Risques identifiés'
    )

    control_ids = fields.Many2many(
        'audit_gainde.control',
        compute='_compute_controls',
        string='Contrôles'
    )
    def _compute_controls(self):
        for mission in self:
            mission.control_ids = mission.risk_ids.mapped('control_ids')

    finding_ids = fields.One2many(
        'audit_gainde.finding',
        'mission_id',
        string='Constats'
    )

    recommendation_ids = fields.One2many(
        'audit_gainde.recommendation',
        'mission_id',
        string='Recommandations'
    )

    corrective_action_ids = fields.One2many(
        'audit_gainde.corrective.action',
        'mission_id',
        string='Actions Correctives'
    )

    # ===========================================
    # DOCUMENTS
    # ===========================================
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'mission_attachment_rel',
        string='Pièces jointes'
    )

    # ===========================================
    # STATS CALCULÉES
    # ===========================================
    risk_count = fields.Integer(
        string='Risques',
        compute='_compute_stats',
        store=True
    )

    finding_count = fields.Integer(
        string='Constats',
        compute='_compute_stats',
        store=True
    )

    recommendation_count = fields.Integer(
        string='Recommendations',
        compute='_compute_stats',
        store=True
    )

    corrective_action_count = fields.Integer(
        string='Actions correctives',
        compute='_compute_stats',
        store=True
    )

    completion_rate = fields.Float(
        string='Taux réalisation (%)',
        compute='_compute_stats',
        store=True,
        help="Avancement hybride : 30% état + 70% sous-éléments"
    )
    is_late = fields.Boolean(
        string="Mission en retard",
        compute="_compute_is_late",
        store=True
    )

    # ===========================================
    # FONCTION QUI PERMET DE CALCULER LE POUCENTAGE DE RECOMMATION REALISEES
    # ===========================================
    recommendation_done_rate = fields.Float(
        string="Taux recommandations mises en œuvre",
        compute="_compute_recommendation_rate",
        store=True,
        aggregator='avg'
    )

    @api.depends('recommendation_ids.state')
    def _compute_recommendation_rate(self):
        for mission in self:
            recommendations = mission.recommendation_ids

            total = len(recommendations)
            done = len(recommendations.filtered(lambda r: r.state in ['implemented', 'closed']))

            mission.recommendation_done_rate = (done / total * 100) if total else 0.0


    @api.model_create_multi
    def create(self, vals_list):
        """Génère référence automatique AUD-2026-0001"""
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('audit_gainde.mission')
        return super().create(vals_list)



    def action_risk_list(self):
        """Ouvre la liste des risques liés"""
        return {
            'name': 'Risques',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.risk',
            'view_mode': 'list,form',
            'domain': [('mission_ids', 'in', self.id)],
            'context': {'default_mission_ids': [(6, 0, [self.id])]},
        }

    def action_finding_list(self):
        """Ouvre la liste des constats liés"""
        return {
            'name': 'Constats',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.finding',
            'view_mode': 'list,form',
            'domain': [('mission_id', '=', self.id)],
            'context': {'default_mission_id': self.id},
        }
    def action_recommendation_list(self):
        """Ouvre la liste des recommendations liés"""
        return {
            'name': 'Recommendations',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.recommendation',
            'view_mode': 'list,form',
            'domain': [('mission_id', '=', self.id)],
            'context': {'default_mission_id': self.id},
        }

    def action_corrective_action_list(self):
        """Ouvre la liste des actions correctives liés"""
        return {
            'name': 'Actions correctives',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.corrective.action',
            'view_mode': 'list,form',
            'domain': [('mission_id', '=', self.id)],
            'context': {'default_mission_id': self.id},
        }



    def action_start_mission(self):
        """Démarre la mission"""
        self.write({'state': 'in_progress'})

    def action_review_mission(self):
        """Passe en revue"""
        self.write({'state': 'review'})

    def action_close_mission(self):
        """Clôture la mission"""
        self.write({'state': 'closed'})

    def action_view_risks(self):
        """Navigation vers les risques"""
        return {
            'name': _('Risques'),
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.risk',
            'view_mode': 'tree,form',
            'domain': [('mission_id', '=', self.id)]
        }

    @api.depends('risk_ids', 'finding_ids','corrective_action_ids','recommendation_ids', 'state', 'finding_ids.state')
    def _compute_stats(self):
        for mission in self:
            mission.risk_count = len(mission.risk_ids)
            mission.finding_count = len(mission.finding_ids)
            mission.recommendation_count = len(mission.recommendation_ids)
            mission.corrective_action_count = len(mission.corrective_action_ids)

            total_items = len(mission.risk_ids) + len(mission.finding_ids)

            if mission.state == 'closed':
                mission.completion_rate = 100.0
            elif mission.state == 'planned':
                mission.completion_rate = 0.0
            else:
                # ÉTAT : 0-30%
                if mission.state == 'in_progress':
                    state_progress = 15.0  # 50% des 30%
                elif mission.state == 'review':
                    state_progress = 30.0  # 100% des 30%
                else:
                    state_progress = 0.0

                # ITEMS : 0-70%
                items_progress = 0.0
                if total_items > 0:
                    treated_items = len(mission.risk_ids) + len(mission.finding_ids.filtered(lambda f: f.state != 'draft'))
                    items_progress = (treated_items / total_items) * 70.0  # Max 70%

                # TOTAL CORRECT
                mission.completion_rate = state_progress + items_progress

    # Statistique des missions en retard
    @api.depends('period_end', 'state')
    def _compute_is_late(self):
        today = fields.Date.today()
        for mission in self:
            mission.is_late = bool(
                mission.period_end and
                mission.period_end < today and
                mission.state != 'closed'
            )

    # Surcharge write pour sécurité serveur
    def write(self, vals):
        for mission in self:
            # Si la mission est clôturée
            if mission.state == 'closed':
                # Autoriser uniquement la modification du champ state
                if set(vals.keys()) != {'state'}:
                    raise UserError("Impossible de modifier une mission clôturée.")
        return super().write(vals)

    def unlink(self):
        if any(mission.state == 'closed' for mission in self):
            raise UserError("Impossible de supprimer une mission clôturé.")
        return super().unlink()

    def action_send_mission_email(self):
        """Bouton ENVOIE MAIL"""
        template = self.env.ref('audit_gainde.email_template_mission_create')
        template.send_mail(self.id, force_send=True)
        return True


            