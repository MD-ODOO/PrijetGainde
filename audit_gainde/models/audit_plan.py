# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date


class AuditGaindePlan(models.Model):
    """
    Modèle principal pour la gestion des PLANS D'AUDIT ANNUELS GLOBAL.

    DESCRIPTION :
    - Conteneur stratégique regroupant TOUTES les missions d'un audit annuel
    - Vue de pilotage avec KPI agrégés (missions, risques, recommandations)
    - PAS de liaison directe avec projet (réservé aux MISSIONS)
    - Workflow : Prévu → Validé → En cours → Clôturé
    - Stats calculées automatiquement depuis les missions enfants
    """
    _name = 'audit_gainde.plan'
    _description = 'Plan d\'audit annuel Gainde'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'year desc'

    # ===========================================
    # CHAMPS IDENTIFICATION & MÉTADONNÉES
    # ===========================================
    name = fields.Char(
        string='Référence',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        help="Référence unique auto-générée (ex: PLAN-2026-0001)"
    )

    year = fields.Char(
        string='Année',
        required=True,
        size=4,
        default=lambda self: str(date.today().year),
        help="Année civile du plan d'audit (ex: 2026)"
    )

    logo = fields.Image(string="Image entête", max_width=256, max_height=256)
    # ===========================================
    # CHAMPS STRATÉGIQUES
    # ===========================================
    strategic_objectives = fields.Html(
        string='Objectifs stratégiques',
        help="Objectifs prioritaires alignés sur la stratégie entreprise"
    )

    planned_missions_count = fields.Integer(
        string='Nombre de missions prévues',
        required=True,
        default=0,
        help="Nombre total de missions prévues dans ce plan"
    )

    # ===========================================
    # RELATIONS HIÉRARCHIQUES
    # ===========================================
    mission_ids = fields.One2many(
        'audit_gainde.mission',
        'plan_id',
        string='Missions d\'audit',
        help="Toutes les missions appartenant à ce plan"
    )

    plan_responsible_id = fields.Many2one(
        'res.users',
        string='Responsable du plan',
        required=True,
        tracking=True,
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('audit_gainde.group_manager').ids)
        ],
        help="Utilisateur responsable de la bonne exécution du plan"
    )

    company_id = fields.Many2one(
        'res.company',
        string='Société',
        default=lambda self: self.env.company,
        help="Société concernée par ce plan d'audit"
    )

    # ===========================================
    # CHAMPS WORKFLOW & STATUT
    # ===========================================
    state = fields.Selection([
        ('draft', 'Prévu'),
        ('in_progress', 'En cours'),
        ('validated', 'Validé'),
        ('closed', 'Clôturé')
    ], string='Statut',
        default='draft',
        tracking=True,
        copy=False,
        required=True,
        help="État d'avancement global du plan d'audit"
    )

    # ===========================================
    # CHAMPS DE SUIVI TEMPORAL
    # ===========================================
    date_start = fields.Date(string='Date de début')
    date_validated = fields.Date(string='Date de validation')
    date_closed = fields.Date(string='Date de clôture')

    # ===========================================
    # KPI CALCULÉS (STATS AGGRÉGÉES)
    # ===========================================
    completed_missions_count = fields.Integer(
        string='Missions réalisées',
        compute='_compute_mission_stats',
        store=True,
        help="Nombre de missions terminées (state='closed')"
    )

    completion_rate = fields.Float(
        string='Taux de réalisation (%)',
        compute='_compute_mission_stats',
        store=True,
        aggregator='avg',
        help="Pourcentage de missions réalisées vs prévues"
    )

    total_risk_count = fields.Integer(
        string='Total risques (toutes missions)',
        compute='_compute_aggregated_stats',
        store=True,
        help="Nombre total de risques identifiés dans toutes les missions"
    )

    total_recommendation_count = fields.Integer(
        string='Total recommandations (toutes missions)',
        compute='_compute_aggregated_stats',
        store=True,
        help="Nombre total de recommandations émises dans toutes les missions"
    )

    recommendation_done_rate = fields.Float(
        string="Taux recommandations appliquées (%)",
        compute="_compute_recommendation_rate",
        store=True
    )


    # =========================
    # KPI MISSIONS PAR STATUT
    # =========================

    mission_planned_count = fields.Integer(
        string="Missions planifiées",
        compute="_compute_mission_kpis",
        store=True
    )


    mission_progress_count = fields.Integer(
        string="Missions en cours",
        compute="_compute_mission_kpis",
        store=True
    )

    mission_done_count = fields.Integer(
        string="Missions terminées",
        compute="_compute_mission_kpis",
        store=True
    )

    mission_late_count = fields.Integer(
        string="Missions en retard",
        compute="_compute_mission_kpis",
        store=True
    )

    @api.depends('mission_ids.state', 'mission_ids.is_late')
    def _compute_mission_kpis(self):
        for plan in self:
            done = plan.mission_ids.filtered(lambda m: m.state == 'closed')
            planned = plan.mission_ids.filtered(lambda m: m.state == 'planned')
            progress = plan.mission_ids.filtered(lambda m: m.state == 'in_progress')
            late = plan.mission_ids.filtered(lambda m: m.is_late)

            plan.mission_done_count = len(done)
            plan.mission_planned_count = len(planned)
            plan.mission_progress_count = len(progress)
            plan.mission_late_count = len(late)

    # ===========================================
    # FONCTION : GÉNÉRATION RÉFÉRENCE AUTOMATIQUE
    # ===========================================
    @api.model_create_multi
    def create(self, vals_list):
        """
        Surcharge de create pour générer automatiquement la référence unique.
        Utilise la séquence 'audit_gainde.plan' définie dans data/audit_sequence.xml
        """
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('audit_gainde.plan') or 'New'
        return super().create(vals_list)

    # ===========================================
    # FONCTION : CALCUL STATS MISSIONS
    # ===========================================
    @api.depends('mission_ids.state', 'planned_missions_count')
    def _compute_mission_stats(self):
        """
        Calcule dynamiquement :
        - Nombre de missions terminées (state='closed')
        - Taux de réalisation = (terminées / prévues) * 100
        """
        for plan in self:

            closed_missions = plan.mission_ids.filtered(
                lambda m: m.state == 'closed'
            )

            plan.completed_missions_count = len(closed_missions)

            if plan.planned_missions_count:
                plan.completion_rate = (
                                               plan.completed_missions_count /
                                               plan.planned_missions_count
                                       ) * 100
            else:
                plan.completion_rate = 0

    # ===========================================
    # FONCTION : CALCUL STATS AGGRÉGÉES
    # ===========================================
    @api.depends('mission_ids.risk_ids', 'mission_ids.finding_ids.recommendation_ids')
    def _compute_aggregated_stats(self):
        """
        Aggrège les statistiques depuis TOUTES les missions :
        - Total des risques identifiés
        - Total des recommandations émises
        """
        for plan in self:
            plan.total_risk_count = len(plan.mission_ids.mapped('risk_ids'))
            plan.total_recommendation_count = len(plan.mission_ids.mapped('finding_ids.recommendation_ids'))



    @api.depends('mission_ids.recommendation_ids.state')
    def _compute_recommendation_rate(self):
        for plan in self:
            recommendations = plan.mission_ids.mapped('recommendation_ids')

            total = len(recommendations)

            done = len(
                recommendations.filtered(
                    lambda r: r.state in ['implemented', 'verified', 'closed']
                )
            )

            plan.recommendation_done_rate = (done / total * 100) if total else 0.0

    # ===========================================
    # FONCTIONS WORKFLOW : VALIDATION
    # ===========================================
    def action_validate_plan(self):
        """
        Passe le plan à l'état 'validated' et enregistre la date.
        Prêt pour démarrage des missions.
        """
        self.write({
            'state': 'validated',
            'date_validated': fields.Date.today()
        })

    # ===========================================
    # FONCTION WORKFLOW : DÉMARRAGE
    # ===========================================
    def action_start_plan(self):
        """
        Lance officiellement le plan d'audit (état 'in_progress').
        Enregistre la date de début effectif.
        """
        self.write({
            'state': 'in_progress',
            'date_start': fields.Date.today()
        })

    # ===========================================
    # FONCTION WORKFLOW : CLÔTURE
    # ===========================================
    def action_close_plan(self):
        """
        Clôture définitivement le plan.
        Vérification : TOUTES les missions doivent être closes.
        """
        if self.mission_ids.filtered(lambda m: m.state != 'closed'):
            raise ValidationError(
                _("Impossible de clôturer le plan tant que toutes les missions ne sont pas clôturées."))
        self.write({
            'state': 'closed',
            'date_closed': fields.Date.today()
        })

    # ===========================================
    # FONCTION WORKFLOW : BROUILLON
    # ===========================================
    def action_draft(self):
        """Remet le plan à l'état brouillon pour modifications."""
        self.write({'state': 'draft'})


    # ===========================================
    # FONCTION : NAVIGATION VERS MISSIONS
    # ===========================================
    def action_view_missions(self):
        """
        Ouvre la vue des missions de ce plan dans une nouvelle fenêtre.
        Filtre automatique sur les missions du plan courant.
        """
        return {
            'name': _('Missions du plan'),
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.mission',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', self.mission_ids.ids)],
            'context': {'default_plan_id': self.id}
        }

    # =========================
    # ACTIONS KPI DASHBOARD
    # =========================
    def action_mission_late(self):
        return {
            'name': 'Missions en retard',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.mission',
            'view_mode': 'list,form',
            'domain': [
                ('plan_id', '=', self.id),
                ('is_late', '=', True)
            ]
        }


    def action_mission_planned(self):
        return {
            'name': 'Missions planifiées',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.mission',
            'view_mode': 'list,form',
            'domain': [
                ('plan_id', '=', self.id),
                ('state', '=', 'planned')
            ]
        }

    def action_mission_progress(self):
        return {
            'name': 'Missions en cours',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.mission',
            'view_mode': 'list,form',
            'domain': [
                ('plan_id', '=', self.id),
                ('state', '=', 'in_progress')
            ]
        }



    def action_mission_done(self):
        return {
            'name': 'Missions terminées',
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.mission',
            'view_mode': 'list,form',
            'domain': [
                ('plan_id', '=', self.id),
                ('state', '=', 'closed')
            ]
        }
    # Surcharge write pour sécurité serveur
    def write(self, vals):
        for plan in self:
            # Si le plan est clôturé
            if plan.state == 'closed':
                # Autoriser uniquement la modification du champ state
                if set(vals.keys()) != {'state'}:
                    raise UserError("Impossible de modifier un plan clôturé.")
        return super().write(vals)

    def unlink(self):
        if any(plan.state == 'closed' for plan in self):
            raise UserError("Impossible de supprimer un plan clôturé.")
        return super().unlink()

