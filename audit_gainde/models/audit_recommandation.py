# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import date, timedelta


class AuditGaindeRecommendation(models.Model):
    """
    Modèle RECOMMANDATIONS émises suite à un constat.

    HIÉRARCHIE : Mission → Finding → Recommendation → Action
    CHAMPS : Responsable, échéance, statut, preuves
    """
    _name = 'audit_gainde.recommendation'
    _description = 'Recommandation d\'audit Gainde'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'reference'

    # ===========================================
    # IDENTIFICATION
    # ===========================================
    reference = fields.Char(
        string='Réf:',
        required=True,
        default='New',
        readonly=True,
        copy=False
    )

    @api.constrains('reference')
    def _check_reference_unique(self):
        for record in self:
            duplicate = self.search([
                ('reference', '=', record.reference),
                ('id', '!=', record.id)
            ])
            if duplicate:
                raise ValidationError(
                    f"La référence {record.reference} existe déjà !"
                )

    description = fields.Text(
        string='Description recommandation',
        required=True
    )

    # ===========================================
    # RELATIONS
    # ===========================================
    finding_id = fields.Many2one(
        'audit_gainde.finding',
        string='Constat lié',
        required=True,
        ondelete='cascade'
    )

    mission_id = fields.Many2one(
        'audit_gainde.mission',
        string='Mission',
        related='finding_id.mission_id',
        store=True,
        readonly=True,
    )

    risk_id = fields.Many2one(
        'audit_gainde.risk',
        string='Risque',
        related='finding_id.risk_id',
        store=True,
        readonly=True,

    )
    
    corrective_action_ids = fields.One2many(
        'audit_gainde.corrective.action',
        'recommendation_id',
        string='Actions Correctives'
    )

    # ===========================================
    # RESPONSABILITÉ
    # ===========================================
    responsible_id = fields.Many2one(
        'res.users',
        string='Responsable mise en œuvre',
        required=True,
        tracking=True
    )

    # ===========================================
    # PLANNING
    # ===========================================
    date_target = fields.Date(
        string='Échéance cible',
        required=True
    )

    date_start = fields.Date(
        string='Date début réel'
    )

    days_delayed = fields.Integer(
        string='Retard (jours)',
        compute='_compute_delay',
        store=True
    )

    # ===========================================
    # STATUT
    # ===========================================
    state = fields.Selection([
        ('open', 'Non traité'),
        ('in_progress', 'En cours'),
        ('implemented', 'Mise en œuvre'),
        ('closed', 'Clôturée')
    ], string='Statut', default='open', tracking=True, group_expand='_group_expand_states')

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, val in self._fields['state'].selection]

    progress = fields.Float(
        string='Avancement (%)',
        compute='_compute_progress',
        store=True,  # Performance dashboard
        readonly=True
    )

    # ===========================================
    # GÉNÉRATION RÉFÉRENCE
    # ===========================================
    @api.model_create_multi
    def create(self, vals_list):
        """Génère référence REC0001, REC0002..."""
        # Pré-générer les codes AVANT create (évite récursion)
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                # Compte les enregistrements existants UNIQUEMENT
                count = self.search_count([]) + 1
                vals['reference'] = f"REC{count:04d}"  # REC0001, REC0002...
        
        # Création SANS récursion
        return super().create(vals_list)

    # ===========================================
    # COMPUTE RETARD
    # ===========================================
    @api.depends('date_target', 'state')
    def _compute_delay(self):
        today = date.today()
        for rec in self:
            if rec.state in ['open', 'in_progress'] and rec.date_target:
                rec.days_delayed = (today - rec.date_target).days
            else:
                rec.days_delayed = 0

    # ===========================================
    # ACTIONS WORKFLOW
    # ===========================================
    def action_start(self):
        """Démarre la mise en œuvre"""
        self.write({
            'state': 'in_progress',
            'date_start': date.today()
        })

    def action_implemented(self):
        """Marque comme mise en œuvre"""
        self.write({'state': 'implemented'})


    def action_close(self):
        """Clôture définitivement"""
        self.write({'state': 'closed'})


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


    @api.depends('state', 'date_target', 'days_delayed', 'date_start')
    def _compute_progress(self):
        today = date.today()
        for rec in self:
            if rec.state == 'closed':
                rec.progress = 100.0
            elif rec.state == 'implemented':
                rec.progress = 85.0
            elif rec.state == 'in_progress':
                if rec.date_start and rec.date_target:
                    total_days = (rec.date_target - rec.date_start).days or 1
                    elapsed_days = max(0, (today - rec.date_start).days)
                    rec.progress = min(75.0, (elapsed_days / total_days) * 75.0)
                else:
                    rec.progress = 40.0
            elif rec.state == 'open':
                base_progress = 10.0
                if rec.days_delayed > 0:
                    rec.progress = max(0.0, base_progress - (rec.days_delayed * 2))
                else:
                    rec.progress = base_progress
            else:
                rec.progress = 0.0

    # Surcharge write pour sécurité serveur
    def write(self, vals):
        for recommendation in self:
            # Si la recommandationt est clôturée
            if recommendation.state == 'closed':
                # Autoriser uniquement la modification du champ state
                if set(vals.keys()) != {'state'}:
                    raise UserError("Impossible de modifier une recommandation clôturée.")
        return super().write(vals)

    def unlink(self):
        if any(recommendation.state == 'closed' for recommendation in self):
            raise UserError("Impossible de supprimer une recommandation clôturée.")
        return super().unlink()


