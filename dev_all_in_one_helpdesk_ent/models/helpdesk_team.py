# -*- coding: utf-8 -*-

from odoo import fields, models, api


class HelpdeskTeam(models.Model):
    _inherit = 'helpdesk.team'
    
    profile_id = fields.Many2one(
        'user.profiles',
        string='Profil utilisateur',
        help="Profil utilisateur associé à cette équipe d'assistance"
    )
    
    allow_multiple_assignment = fields.Boolean(
        string='Affectation multiple',
        default=False,
        help="Permet d'affecter plusieurs utilisateurs à un ticket de cette équipe"
    )


