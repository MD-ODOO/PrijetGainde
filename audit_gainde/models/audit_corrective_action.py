# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class AuditGaindeCorrectiveAction(models.Model):
    """
    Modèle ACTIONS CORRECTIVES concrètes suite aux recommandations.

    HIÉRARCHIE : Mission → Finding → Recommendation → Corrective Action
    SUIVI : % avancement, preuves, échéances, relances automatiques
    """
    _name = 'audit_gainde.corrective.action'
    _description = 'Action corrective Gainde'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_target'
    _rec_name = 'reference'

    # ===========================================
    # IDENTIFICATION
    # ===========================================
    reference = fields.Char(
        string='Réf. action',
        required=True,
        default='New',
        readonly=True,
        copy=False
    )

    notes = fields.Html(string='Description')

    # ===========================================
    # RELATIONS HIÉRARCHIQUES
    # ===========================================
    recommendation_id = fields.Many2one(
        'audit_gainde.recommendation',
        string='Recommandation',
        required=True,
        ondelete='cascade'
    )

    finding_id = fields.Many2one(
        'audit_gainde.finding',
        string='Constat',
        related='recommendation_id.finding_id',
        store=True,
    )

    mission_id = fields.Many2one(
        'audit_gainde.mission',
        string='Mission',
        store=True,
        related='recommendation_id.mission_id',
    )

    # ===========================================
    # PRIORITÉ & RESPONSABLE
    # ===========================================
    priority = fields.Selection([
        ('0', 'Faible'),
        ('1', 'Normale'),
        ('2', 'Haute'),
        ('3', 'Urgente')
    ], string='Priorité', default='1')

    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable',
        related='recommendation_id.responsible_id',
        required=True,
        tracking=True
    )

    # ===========================================
    # PLANNING & SUIVI
    # ===========================================
    date_start = fields.Date(
        string='Date début',
        default=date.today()
    )

    date_target = fields.Date(
        string='Date terminée '
    )

    date_completed = fields.Date(string='Date cible')

    progress = fields.Float(
        string='Avancement (%)',
        compute='_compute_progress',
        store=True,
        readonly=True,
    )

    days_remaining = fields.Integer(
        string='Jours restants',
        compute='_compute_timing',
        store=True
    )

    days_delayed = fields.Integer(
        string='Retard (jours)',
        compute='_compute_timing',
        store=True
    )

    # ===========================================
    # STATUT
    # ===========================================
    state = fields.Selection([
        ('planned', 'Planifiée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('verified', 'Vérifiée'),
        ('closed', 'Clôturée')
    ], string='Statut', default='planned', tracking=True, group_expand='_group_expand_states')

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, val in self._fields['state'].selection]
    # ===========================================
    # PREUVES
    # ===========================================
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Preuves'
    )

    reminder_sent = fields.Boolean(
        string='Rappel envoyé',
        default=False,
        readonly=True,
        help="Relance automatique 10j avant envoyée"
    )

    # ===========================================
    # GÉNÉRATION RÉFÉRENCE
    # ===========================================
    @api.model_create_multi
    def create(self, vals_list):
        """Génère AC001, AC002..."""
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                count = self.search_count([]) + 1
                vals['reference'] = f"AC{count:03d}"  # ← 3 chiffres : AC001
        
        return super().create(vals_list)

    # ===========================================
    # CALCUL TIMING
    # ===========================================
    @api.depends('date_target', 'state', 'date_completed')
    def _compute_timing(self):
        today = date.today()
        for action in self:
            if action.state in ['planned', 'in_progress']:
                if action.date_target:
                    delta = action.date_target - today
                    action.days_remaining = delta.days
                    action.days_delayed = max(0, -delta.days)
                else:
                    action.days_remaining = 0
                    action.days_delayed = 0
            else:
                action.days_remaining = 0
                action.days_delayed = 0

    # ===========================================
    # WORKFLOW ACTIONS
    # ===========================================


    def action_planned(self):
        """Retour sur Planifiée"""
        self.write({'state': 'planned',
        'date_start': date.today()
        })
        
    def action_in_progress(self):
        """Passe en cours"""
        self.write({'state': 'in_progress',
        'date_start': date.today()
        })

    def action_completed(self):
        """Marque terminée"""
        self.write({
            'state': 'completed',
            'date_completed': date.today()
        })

    def action_verify(self):
        """Demande vérification"""
        self.write({'state': 'verified'})

    def action_close(self):
        """Clôture définitivement"""
        self.write({'state': 'closed'})

    # ===========================================
    # RELANCE AUTOMATIQUE (10 jours avant)
    # ===========================================
    def cron_send_reminders(self):
        """Relance 10 jours avant échéance"""
        today = date.today()
        reminder_date = today + timedelta(days=10)

        pending = self.search([
            ('state', 'in', ['open', 'in_progress']),
            ('date_target', '=', reminder_date)
        ])

        for action in pending:
            action.message_post(
                body=_("**RELANCE** : Échéance approche le %s") % action.date_target,
                subject="Action corrective en retard",
                partner_ids=action.responsible_id.partner_id.ids
            )

    # ===========================================
    # NAVIGATION
    # ===========================================
    def action_view_attachments(self):
        return {
            'name': _('Preuves'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.attachment_ids.ids)]
        }

    @api.depends('state', 'date_target', 'days_delayed', 'date_start', 'date_completed')
    def _compute_progress(self):
        """CALCUL PROGRESSION Actions Correctives (même logique que Recommandations)"""
        today = date.today()

        for action in self:
            if action.state == 'closed':
                action.progress = 100.0

            elif action.state == 'verified':
                action.progress = 95.0

            elif action.state == 'completed':
                action.progress = 85.0  # Terminée mais non vérifiée

            elif action.state == 'in_progress':
                # PROGRESSION TEMPORELLE (0-75%)
                if action.date_start and action.date_target:
                    total_days = (action.date_target - action.date_start).days or 1
                    elapsed_days = max(0, (today - action.date_start).days)
                    action.progress = min(75.0, (elapsed_days / total_days) * 75.0)
                else:
                    action.progress = 40.0

            elif action.state == 'open':
                # 📋 BASE 10% + Pénalité retard
                base_progress = 10.0
                if action.days_delayed > 0:
                    action.progress = max(0.0, base_progress - (action.days_delayed * 2))
                else:
                    action.progress = base_progress

            elif action.state == 'draft':
                action.progress = 0.0
            else:
                action.progress = 0.0

    def cron_send_reminders(self):
        """Relance 10j AVANT → UNE SEULE FOIS par action"""
        today = date.today()

        reminder_date = today + timedelta(days=10)

        pending = self.search([
            ('state', 'in', ['planned', 'in_progress']),
            ('date_target', '=', reminder_date),
            ('responsible_id', '!=', False),
            ('reminder_sent', '=', False)  # ← UNIQUEMENT si PAS encore envoyé
        ])

        for action in pending:
            # ENVOIE MAIL
            template = self.env.ref('audit_gainde.email_template_action_reminder')
            template.send_mail(action.id, force_send=True)

            #MARQUE COMME ENVOYÉ (évite doublons)
            action.write({'reminder_sent': True})

    # Surcharge write pour sécurité serveur
    def write(self, vals):
        for corrective in self:
            # Si l'action corrective est clôturée
            if corrective.state == 'closed':
                # Autoriser uniquement la modification du champ state
                if set(vals.keys()) != {'state'}:
                    raise UserError("Impossible de modifier une action corrective clôturée.")
        return super().write(vals)

    def unlink(self):
        if any(corrective.state == 'closed' for corrective in self):
            raise UserError("Impossible de supprimer une action corrective clôturée.")
        return super().unlink()

