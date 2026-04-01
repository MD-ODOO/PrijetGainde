# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging

log = logging.getLogger(__name__)

class DocumentRefusalMotivation(models.TransientModel):
    _name = "nrt.holidays.refusal.motivation"
    _description = "Motivation de refus de congé"

    holiday_request = fields.Many2one(
        'hr.leave', string='Demande de congé', readonly=True
    )
    motivation = fields.Text(string='Motivation', required=True)

    @api.model
    def default_get(self, fields_list):
        """Pré-remplit le champ holiday_request avec l'objet actif."""
        res = super().default_get(fields_list)
        active_ids = self._context.get('active_ids', [])
        if active_ids:
            res['holiday_request'] = active_ids[0]
        return res

    def refuse(self):
        """Applique le refus avec la motivation."""
        if not self.holiday_request:
            return
        self.holiday_request.refusal_motivation = self.motivation
        if self.holiday_request.request_type != 'remove':
            # Pour les types autres que congé "removal", remettre en brouillon
            self.holiday_request.state = 'draft'
        else:
            # Utiliser la méthode de refus standard pour les congés classiques
            self.holiday_request.action_refuse()
