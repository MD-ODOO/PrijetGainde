from odoo import models, fields, _


class LegalContractAmendment(models.Model):
    _name = 'legal.contract.amendment'
    _description = 'Avenant au Contrat'
    _inherit = ['mail.thread', 'mail.activity.mixin','abstract.signable.document']


    name = fields.Char(string="Référence Avenant", required=True)
    contract_id = fields.Many2one('legal.contract', string="Contrat", required=True, ondelete='cascade')
    date = fields.Date(string="Date Avenant", default=fields.Date.today)
    description = fields.Text(string="Description")
    stage_id = fields.Many2one('legal.contract.amendment.stage', string="Étape",
                               tracking=True,
                               default=lambda self: self.env.ref(
                                   'gainde_legal_contract.amendment_stage_draft',
                                   raise_if_not_found=False))
    stage_id_name = fields.Char(related='stage_id.name',
                                string="Nom de l'étape", store=True)
    document_ids = fields.Many2many(
        'ir.attachment',
        'legal_amendment_ir_attachment_rel',
        'amendment_id',
        'attachment_id',
        string="Documents liés",
        help="Avenants scannés, versions signées, annexes...",
        copy=False,
        tracking=True,
    )


    def _update_stage_after_sign(self):
        """
        Optionnel : Si l'avenant n'a pas de stage_id, on peut notifier le contrat parent
        """
        if self.contract_id:
            self.contract_id.message_post(
                body="L'avenant %s a été signé numériquement." % self.name
            )

    def action_set_sent(self):
        stage = self.env.ref('gainde_legal_contract.amendment_stage_sent')
        self.write({'stage_id': stage.id})
        self.message_post(
            body=_("L'avenant a été envoyé pour signature."),
            subtype_xmlid="mail.mt_comment"
        )

    def action_set_signed(self):
        stage = self.env.ref('gainde_legal_contract.amendment_stage_signed')
        self.write({'stage_id': stage.id})
        self.message_post(
            body=_("✅ <strong>L'avenant a été signé et validé.</strong>"),
            subtype_xmlid="mail.mt_comment"
        )
        # Optionnel : Notifier aussi sur le contrat parent
        if self.contract_id:
            self.contract_id.message_post(
                body=_("Un nouvel avenant (%s) a été signé.") % self.name)

    def action_set_revised(self):
        stage = self.env.ref('gainde_legal_contract.amendment_stage_revised')
        self.write({'stage_id': stage.id})
        self.message_post(
            body=_("L'avenant est renvoyé en révision."),
            subtype_xmlid="mail.mt_comment"
        )


    # def action_send_for_signature(self):
    #     """ Passage du brouillon à l'envoi """
    #     self.ensure_one()
    #     # Ici vous pouvez ajouter la logique d'envoi d'email ou Odoo Sign
    #     self.sign_status = 'sent'

    # def action_set_signed(self):
    #     """ Confirmation de la signature """
    #     self.ensure_one()
    #     self.sign_status = 'signed'
    #
    # def action_set_revised(self):
    #     """ En cas de refus """
    #     self.ensure_one()
    #     self.sign_status = 'revised'


