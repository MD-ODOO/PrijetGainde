# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class AuditGaindeFinding(models.Model):
    """
    Modèle CONSTATS d'audit découverts lors d'une mission.

    HIÉRARCHIE : Mission → [Risk →] Finding → Recommendation
    LIENS : Une mission, un risque optionnel, plusieurs recommandations
    """
    _name = 'audit_gainde.finding'
    _description = 'Constat d\'audit Gainde'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'reference'

    # ===========================================
    # IDENTIFICATION
    # ===========================================
    reference = fields.Char(
        string='Réf. constat',
        required=True,
        default='New',
        readonly=True,
        copy=False
    )

    name = fields.Text(
        string='Description constat',
        required=True
    )

    # ===========================================
    # RELATIONS OBLIGATOIRES
    # ===========================================
    mission_id = fields.Many2one(
        'audit_gainde.mission',
        string='Mission audit',
        required=True,
        ondelete='cascade'
    )

    # ===========================================
    # RELATION OPTIONNELLE
    # ===========================================
    risk_id = fields.Many2one(
        'audit_gainde.risk',
        string='Risque lié',
        ondelete='cascade',
        required=True,
    )

    # ===========================================
    # GRAVITÉ
    # ===========================================
    severity = fields.Selection([
        ('minor', 'Mineur'),
        ('major', 'Majeur'),
        ('critical', 'Critique')
    ], string='Gravité', required=True, default='minor')

    # ===========================================
    # STATUT
    # ===========================================
    state = fields.Selection([
        ('draft', 'En cours'),
        ('closed', 'Clôturé')
    ], string='Statut', default='draft', tracking=True)

    # ===========================================
    # LIENS VERS RECOMMANDATIONS 
    # ===========================================
    recommendation_ids = fields.One2many(
        'audit_gainde.recommendation',
        'finding_id',
        string='Recommandations'
    )

    # ===========================================
    # GÉNÉRATION RÉFÉRENCE
    # ===========================================
    # Surcharge du create pour générer une référence unique du type C001, C002, ... à la création d'un constat
    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                count = self.search_count([]) + 1
                vals['reference'] = f"C{count:03d}"

        findings = super().create(vals_list)

        # Lier le risque à la mission si pas déjà fait
        for finding in findings:

            if finding.risk_id and finding.mission_id:

                # évite les doublons
                if finding.risk_id not in finding.mission_id.risk_ids:
                    finding.mission_id.write({
                        'risk_ids': [(4, finding.risk_id.id)]
                    })

        return findings



    # ===========================================
    # ACTIONS WORKFLOW
    # ===========================================

    def action_draft_finding(self):
        """Remetre en brouillon"""        
        
        self.write({'state': 'draft'})
  
    def action_close_finding(self):
        """Clôture si toutes les reco sont faites"""
        if not self.recommendation_ids:
            raise ValidationError(_("Vous ne pouvez pas cloturer un constat sans recommandation"))
        
        # Vérifier que TOUTES les recommandations sont clôturées
        reco_non_clos = self.recommendation_ids.filtered(lambda r: r.state != 'closed')
        if reco_non_clos:
            raise ValidationError(_(
                "Impossible de cloturer : %d recommandation(s) non cloturee(s) :\n%s" % 
                (len(reco_non_clos), ', '.join(reco_non_clos.mapped('reference')))
            ))
        
        self.write({'state': 'closed'})
        
        


    # ===========================================
    # NAVIGATION
    # ===========================================
    def action_view_recommendations(self):
        return {
            'name': _('Recommandations'),
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.recommendation',
            'view_mode': 'list,form',
            'domain': [('finding_id', '=', self.id)]
        }

    def action_view_mission(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'audit_gainde.mission',
            'res_id': self.mission_id.id,
            'view_mode': 'form'
        }

    # Surcharge write pour sécurité serveur
    def write(self, vals):
        for finding in self:
            # Si le constat est clôturé
            if finding.state == 'closed':
                # Autoriser uniquement la modification du champ state
                if set(vals.keys()) != {'state'}:
                    raise UserError("Impossible de modifier un constat clôturé.")
        return super().write(vals)

    # Surcharge unlink pour sécurité serveur
    def unlink(self):

        if any(finding.state == 'closed' for finding in self):
            raise UserError("Impossible de supprimer un constat clôturé.")

        # mémoriser mission et risque avant suppression
        data = [(f.mission_id, f.risk_id) for f in self]

        res = super().unlink()

        # après suppression, vérifier si les risques liés à ces constats sont encore liés à d'autres constats de la même mission
        for mission, risk in data:

            if mission and risk:

                other = self.search([
                    ('mission_id', '=', mission.id),
                    ('risk_id', '=', risk.id)
                ], limit=1)

                if not other:
                    mission.write({
                        'risk_ids': [(3, risk.id)]
                    })

        return res

