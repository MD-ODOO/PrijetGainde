from odoo import models, fields, api, _
from odoo.exceptions import UserError


class LegalLitigation(models.Model):
    _name = 'legal.litigation'
    _description = 'Contentieux Juridique'
    _inherit = ['mail.thread', 'mail.activity.mixin',
                'abstract.signable.document']

    name = fields.Char(string="Référence Contentieux", required=True,
                       tracking=True)
    contract_id = fields.Many2one('legal.contract', string="Contrat Lié")
    partner_ids = fields.Many2many('res.partner', string="Parties Impliquées")

    stage_id = fields.Many2one('legal.litigation.stage', string="Étape",
                               tracking=True,
                               group_expand='_read_group_stage_ids',
                               default=lambda self: self.env[
                                   'legal.litigation.stage'].search([],
                                                                    limit=1),
                               copy=False)
    stage_id_name = fields.Char(related='stage_id.name',
                                string="Nom de l'étape", store=True)
    is_folded = fields.Boolean(related='stage_id.fold', string="Étape pliée",
                               store=True)
    provision_amount = fields.Monetary(string="Montant Provision Comptable",
                                       currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda
        self: self.env.company.currency_id)
    journal_entry_id = fields.Many2one('account.move',
                                       string="Écriture Comptable",
                                       readonly=True)
    impact_org = fields.Html(string="Impact Organisationnel")
    document_ids = fields.Many2many(
        'ir.attachment',
        'legal_litigation_ir_attachment_rel',
        'litigation_id',
        'attachment_id',
        string="Documents liés",
        help="Pièces du litige : courriers, jugements, preuves, etc.",
        domain="[('mimetype', 'in', ['application/pdf'])]",
        copy=False,
        tracking=True,
    )

    def action_create_provision(self):
        if self.journal_entry_id:
            raise UserError(_("Provision déjà créée."))
        journal = self.env['account.journal'].search(
            [('type', '=', 'general')], limit=1)
        if not journal:
            raise UserError(_("Aucun journal général trouvé."))
        account_provision = self.env['account.account'].search(
            [('code', '=', '6811')], limit=1)  # Exemple code compte, adapte
        if not account_provision:
            raise UserError(_("Compte de provision non trouvé."))
        move_vals = {
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': _("Provision pour %s") % self.name,
            'line_ids': [(0, 0, {
                'account_id': account_provision.id,
                'debit': self.provision_amount,
                'credit': 0,
            }), (0, 0, {
                'account_id': self.env.company.account_journal_suspense_account_id.id,
                # Contrepartie, adapte
                'debit': 0,
                'credit': self.provision_amount,
            })]
        }
        move = self.env['account.move'].create(move_vals)
        move.action_post()
        self.journal_entry_id = move
        self.message_post(body=_("Provision créée : %s") % move.name)

    @api.model
    def _read_group_stage_ids(self, stages, domain, order=None):
        """ Retourne toutes les étapes, même celles sans contentieux """
        search_domain = []
        return self.env['legal.litigation.stage'].sudo().search(search_domain,
                                                                order=order)

    def action_set_stage_analysis(self):
        stage = self.env['legal.litigation.stage'].search(
            [('name', 'ilike', 'Analyse')], limit=1)
        if stage:
            self.stage_id = stage
            self.message_post(body=_("🔍 Dossier passé en <b>Analyse</b> pour étude juridique."))

    def action_set_stage_procedure(self):
        stage = self.env['legal.litigation.stage'].search(
            [('name', 'ilike', 'Procédure Judiciaire')], limit=1)
        if stage:
            self.stage_id = stage
            self.message_post(body=_("⚖️ Lancement de la <b>Procédure Judiciaire</b>."))

    def action_set_stage_won(self):
        stage = self.env.ref('legal_contract_management.stage_closed_won')
        self.stage_id = stage
        self.message_post(body=_("🎉 <b>Litige Gagné !</b> Le dossier est clos avec succès."))

    def action_set_stage_classified(self):
        stage = self.env.ref('legal_contract_management.stage_closed_classified')
        self.stage_id = stage
        self.message_post(body=_("📂 Dossier <b>Classé sans suite</b>."))

    def action_set_stage_lost(self):
        stage = self.env.ref('legal_contract_management.stage_closed_lost')
        self.stage_id = stage
        self.message_post(body=_("📉 <b>Litige Perdu</b>. Le dossier est clôturé."))

    def action_set_stage_next(self):
        stage = self.env.ref('legal_contract_management.stage_closed_next')
        self.stage_id = stage
        self.message_post(body=_("➡️ Dossier transféré à une <b>Instance Supérieure</b>."))

    def action_set_stage_cancelled(self):
        stage = self.env.ref('legal_contract_management.stage_cancelled')
        self.stage_id = stage
        self.message_post(body=_("🚫 <b>Procédure annulée</b>."))

    def _update_stage_after_sign(self):
        """ Recherche l'étape 'Signé' de manière dynamique selon le modèle """
        self.ensure_one()
        if hasattr(self, 'stage_id'):
            stage_model = self.fields_get(['stage_id'])['stage_id']['relation']
            signed_stage = self.env[stage_model].search([
                ('name', 'ilike', 'Signé')
            ], limit=1)

            if signed_stage:
                self.stage_id = signed_stage
