# -*- coding: utf-8 -*-
from odoo import models, fields, api

class RequestMedicalWizard(models.TransientModel):
    _name = "request.medical.wizard"
    _description = "Wizard pour approbation de demande médicale"

    request_id = fields.Many2one('cerco.request.medical', string='Demande', required=True)
    comment = fields.Text(string='Commentaire', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['request_id'] = active_ids[0]
        return res

    def approve(self):
        for wiz in self:
            # Créer un enregistrement approbateur
            self.env['request.medical.approver'].create({
                'request_id': wiz.request_id.id,
                'user_id': self.env.uid,
                'date_approved': fields.Datetime.now(),
                'state': 'validate',
                'comment': wiz.comment,
            })
            # Mettre à jour l'état de la demande
            wiz.request_id.state = 'validate'


class RequestMedicalWizardRefusal(models.TransientModel):
    _name = "request.medical.refusal"
    _description = "Wizard pour refus de demande médicale"

    request_id = fields.Many2one('cerco.request.medical', string='Demande', required=True)
    comment = fields.Text(string='Commentaire', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids', [])
        if active_ids:
            res['request_id'] = active_ids[0]
        return res

    def refuse(self):
        for wiz in self:
            # Créer un enregistrement approbateur avec refus
            self.env['request.medical.approver'].create({
                'request_id': wiz.request_id.id,
                'user_id': self.env.uid,
                'date_approved': fields.Datetime.now(),
                'state': 'cancel',
                'comment': wiz.comment,
            })
            # Mettre à jour l'état de la demande
            wiz.request_id.state = 'cancel'
