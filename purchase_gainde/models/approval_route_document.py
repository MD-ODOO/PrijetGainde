from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, AccessError

from . import selection


class ApprovalRouteDocument(models.AbstractModel):
    _inherit = 'approval.route.document'

    # Rendre les étapes d'approbation éditables côté documents dans purchase_gainde
    approval_route_stage_ids = fields.One2many(
        string='Approval Stages',
        comodel_name='approval.route.document.stage',
        inverse_name='res_id',
        domain=lambda self: [('res_model', '=', self._name)],
        readonly=False,
    )

    def _build_approval_message(self, record):
        """Construire sujet et corps du message d'approbation en français.

        Réutilisé par les différentes méthodes d'envoi (_action_send_to_approve,
        _action_send_to_rnd_approve, _action_send_to_nomail_approve).
        """
        # Cas spécifique : approbation de fiche article (product.template)
        # -> pas de notion de montant, message simplifié et orienté "création/modification d'article".
        if record._name == 'product.template':
            subject = _("Demande d'approbation de produit : %s") % (record.display_name,)

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
            product_url = "%s/web#id=%s&model=product.template&view_type=form&action=product.product_template_action_all" % (
                base_url,
                record.id,
            )

            body_lines = [
                _("Bonjour,"),
                "",
                _(
                    "Vous êtes invité à approuver la création ou la mise à jour de la fiche article : \"%s\"."
                )
                % (record.display_name,),
                "",
                _("Accès direct à la fiche : %s") % product_url,
                "",
                _("Merci de vous connecter au système pour enregistrer votre décision."),
            ]

            message_body = "\n".join(body_lines)
            return subject, message_body

        def _approval_parent_document(rec):
            """Retourne un document parent 'racine' pour les modèles de type ligne.

            Ex: purchase.request.line -> purchase.request (via request_id)
                purchase.order.line -> purchase.order (via order_id)
                account.move.line -> account.move (via move_id)
            """
            parent_field_names = (
                'request_id',
                'order_id',
                'move_id',
                'picking_id',
                'sheet_id',
                'expense_sheet_id',
            )
            for field_name in parent_field_names:
                parent = getattr(rec, field_name, False)
                if parent and getattr(parent, '_name', False):
                    return parent
            return False

        def _approval_doc_type(rec):
            # Utiliser ir.model.name (traduisible) si disponible.
            model = self.env['ir.model']._get(rec._name) if rec and getattr(rec, '_name', False) else False
            return (model.name if model else getattr(rec, '_description', False) or rec._name)

        def _approval_doc_name(rec):
            return getattr(rec, 'display_name', False) or getattr(rec, 'name', False) or str(rec.id)

        # Cas spécifique : approbation d'une ligne de demande d'achat.
        # Par défaut, record._description vaut souvent "Purchase Request Line", ce qui n'est pas lisible
        # côté utilisateurs et peut induire en erreur. On se base plutôt sur la demande parente.
        if record._name == 'purchase.request.line':
            request = getattr(record, 'request_id', False)
            request_name = request.display_name if request else record.display_name

            subject = _("Demande d'approbation : %s") % (request_name,)

            line_desc = (getattr(record, 'description', False)
                         or getattr(record, 'name', False)
                         or getattr(record, 'display_name', ''))
            qty = (getattr(record, 'product_qty', False)
                   or getattr(record, 'quantity', False)
                   or getattr(record, 'product_uom_qty', False))

            line_text = f"    - {line_desc}"
            if qty:
                line_text += f" | Qté : {qty}"

            body_lines = [
                _("Bonjour,"),
                "",
                _("Vous êtes invité à approuver la demande d'achat : \"%s\".") % (request_name,),
                "",
                _("Ligne concernée :"),
                line_text,
                "",
                _("Merci de vous connecter au système pour enregistrer votre décision."),
            ]

            message_body = "\n".join(body_lines)
            return subject, message_body

        # Récupération des lignes potentiellement à approuver
        lines = getattr(record, 'order_line', False) or getattr(record, 'line_ids', False)

        lignes_details = ""
        if lines:
            max_lines = 10
            for index, line in enumerate(lines):
                if index >= max_lines:
                    lignes_details += "\n    - [...]"
                    break

                # Libellé de la ligne
                line_desc = getattr(line, 'description', False) or \
                            getattr(line, 'name', False) or \
                            getattr(line, 'display_name', '')

                qty = (getattr(line, 'product_qty', False)
                       or getattr(line, 'quantity', False)
                       or getattr(line, 'product_uom_qty', False))
                subtotal = getattr(line, 'price_subtotal', False) or getattr(line, 'subtotal', False) or 0.0

                line_text = f"    - {line_desc}"
                if qty:
                    line_text += f" | Qté : {qty}"
                if subtotal:
                    line_text += f" | Montant HT : {subtotal:.2f}"

                lignes_details += "\n" + line_text

        # Montant total du document
        total_amount = (getattr(record, 'amount_total', False)
                        or getattr(record, 'total_amount', False)
                        or 0.0)
        currency = (getattr(record, 'currency_id', False)
                    or getattr(getattr(record, 'company_id', False), 'currency_id', False))

        if currency:
            montant_total_txt = "%.2f %s" % (total_amount, currency.name)
        else:
            montant_total_txt = "%.2f" % total_amount if total_amount else ""  # pragma: no cover

        # Sujet plus explicite
        subject = _("Demande d'approbation : %s") % (_approval_doc_name(_approval_parent_document(record) or record),)

        # Corps du message en français
        doc_record = _approval_parent_document(record) or record
        body_lines = [
            _("Bonjour,"),
            "",
            _(
                "Vous êtes invité à approuver le document « %(doc_type)s » : \"%(doc_name)s\"."
            ) % {
                'doc_type': _approval_doc_type(doc_record),
                'doc_name': _approval_doc_name(doc_record),
            },
        ]

        if montant_total_txt:
            body_lines.append(_("Montant total : %s.") % montant_total_txt)

        if lignes_details:
            body_lines.append("")
            body_lines.append(_("Lignes concernées :"))
            body_lines.append(lignes_details)

        body_lines.extend([
            "",
            _("Merci de vous connecter au système pour enregistrer votre décision."),
        ])

        message_body = "\n".join(body_lines)
        return subject, message_body

    def _action_send_to_approve(self):
        """Envoyer une demande d'approbation avec un message plus riche.

        - Message en français
        - Sujet explicite
        - Contenu listant les lignes et les montants
        - Expéditeur neutre (partenaire de la société au lieu de l'utilisateur)
        """
        for record in self:
            if not record.next_approval_stage_id:
                continue

            stage = record.next_approval_stage_id
            partners = stage.user_ids.mapped('partner_id')

            # Si aucun approbateur n'est configuré sur l'étape suivante,
            # on bloque avec un message explicite plutôt que d'envoyer
            # une notification sans destinataire.
            if not partners:
                raise UserError(_(
                    "Aucun approbateur n'est défini pour l'étape d'approbation suivante de ce document. "
                    "Merci de vérifier la configuration de la route d'approbation."
                ))

            subject, message_body = self._build_approval_message(record)

            if record._name == 'product.template':
                # Keep the same notification style as purchase request/order flows
                # to avoid inconsistent email rendering in some clients.
                record.message_post(
                    body=message_body,
                    partner_ids=partners.ids,
                )
            else:
                # Utiliser le partenaire de la société comme auteur (expéditeur neutre)
                company = getattr(record, 'company_id', False) or self.env.company
                author_partner = company.partner_id if company else False

                record.message_post(
                    body=message_body,
                    subject=subject,
                    partner_ids=partners.ids,
                    message_type='notification',
                    author_id=author_partner.id if author_partner else False,
                )

            stage.sudo().state = 'pending'

    # Gainde customizations for approval.route.document can be added here
    def action_make_apply_no_sms_decision(self, decision):
        for record in self:
            approval_stage = record.current_approval_stage_id
            if not record.current_approval_stage_id:
                raise UserError(_('This %s is not under approval!') % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            decision_label = {
                selection.APPROVAL_STATE_APPROVED: _("approuvé"),
                selection.APPROVAL_STATE_REJECTED: _("rejeté"),
                selection.APPROVAL_STATE_PENDING: _("en attente"),
            }.get(decision, decision)
            record.message_post(
                body=_("%(doc)s : %(decision)s par %(user)s.") % {
                    'doc': getattr(record, 'display_name', False) or self._description,
                    'decision': decision_label,
                    'user': self.env.user.name,
                }
            )

            if decision == selection.APPROVAL_STATE_APPROVED:
                # If user approved document, state is changed according to approval type (one or all)
                if approval_stage.approval_type == selection.APPROVAL_TYPE_ONE:
                    approval_stage.state = decision
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_ALL:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
            elif decision == selection.APPROVAL_STATE_REJECTED:
                # If user rejected document, state is changed as "rejected"
                approval_stage.state = decision

            if record._is_fully_approved():
                record.message_post(
                    body=_("Le document a été entièrement approuvé : %s") % (
                        getattr(record, 'display_name', False) or self._description,
                    )
                )
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
    
                record._action_send_to_nomail_approve()

    def action_make_apply_rnd_decision(self, decision):
        for record in self:
            approval_stage = record.current_approval_stage_id
            if not record.current_approval_stage_id:
                raise UserError(_('This %s is not under approval!') % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            decision_label = {
                selection.APPROVAL_STATE_APPROVED: _("approuvé"),
                selection.APPROVAL_STATE_REJECTED: _("rejeté"),
                selection.APPROVAL_STATE_PENDING: _("en attente"),
            }.get(decision, decision)
            record.message_post(
                body=_("%(doc)s : %(decision)s par %(user)s.") % {
                    'doc': getattr(record, 'display_name', False) or self._description,
                    'decision': decision_label,
                    'user': self.env.user.name,
                }
            )

            if decision == selection.APPROVAL_STATE_APPROVED:
                # If user approved document, state is changed according to approval type (one or all)
                if approval_stage.approval_type == selection.APPROVAL_TYPE_ONE:
                    approval_stage.state = decision
                elif approval_stage.approval_type == selection.APPROVAL_TYPE_ALL:
                    decisions_set = set()
                    for approver in approvers:
                        decisions_set.add(decisions.get(str(approver.id), selection.APPROVAL_STATE_PENDING))
                    # If all approvers approved document, state is changed as "approved", else as "pending"
                    approval_stage.state = decision if decisions_set == {decision} else \
                        selection.APPROVAL_STATE_PENDING
            elif decision == selection.APPROVAL_STATE_REJECTED:
                # If user rejected document, state is changed as "rejected"
                approval_stage.state = decision

            if record._is_fully_approved():
                record.message_post(
                    body=_("Le document a été entièrement approuvé : %s") % (
                        getattr(record, 'display_name', False) or self._description,
                    )
                )
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:
               
                record._action_send_to_rnd_approve()

   
    def _action_send_to_rnd_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            subject, message_body = self._build_approval_message(record)

            partner_ids_set = set()
            user_ids_set = set()
            for line in record.line_ids:
                product = line.product_id
                categ = product.categ_id if product else False
                profile = getattr(categ, 'user_profile_id', False)
                if profile:
                    #raise UserError(_('Profile trouvé: %s') % profile.name)
                    for user in getattr(profile, 'access_user_ids', self.env['res.users']):
                        if user.partner_id:
                            user_ids_set.add(user.id)
                            partner_ids_set.add(user.partner_id.id)

            # Utiliser le partenaire de la société comme auteur (expéditeur neutre)
            company = getattr(record, 'company_id', False) or self.env.company
            author_partner = company.partner_id if company else False

            # Si aucun approbateur n'est trouvé sur cette étape, lever une erreur explicite
            if not partner_ids_set:
                raise UserError(_(
                    "Aucun approbateur n'est défini pour l'étape R&D de ce document. "
                    "Merci de vérifier la configuration des profils R&D ou des étapes d'approbation."
                ))

            record.message_post(
                body=message_body,
                subject=subject,
                partner_ids=list(partner_ids_set),
                message_type='notification',
                author_id=author_partner.id if author_partner else False,
            )
            record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})

            if record.next_approval_stage_id:

                record.next_approval_stage_id.sudo().state = 'pending'
                #record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})
                #raise AccessError(record.current_approval_stage_id.user_ids.ids)

    def _action_send_to_nomail_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            # On conserve le principe "no mail" : pas d'envoi à des partenaires,
            # mais on loggue un message interne cohérent en français.
            subject, message_body = self._build_approval_message(record)

            company = getattr(record, 'company_id', False) or self.env.company
            author_partner = company.partner_id if company else False

            record.message_post(
                body=message_body,
                subject=subject,
                message_type='comment',  # commentaire interne, pas de destinataires explicites
                author_id=author_partner.id if author_partner else False,
            )
            record.next_approval_stage_id.sudo().state = 'pending'
   

class ApprovalRouteDocumentStage(models.Model):
    _inherit = 'approval.route.document.stage'

    def write(self, vals):
        """Contrôler et notifier les modifications d'approbateurs.

        - Par défaut, les étapes sont considérées en lecture seule.
        - Les modifications provenant du front portent le contexte
          ``gainde_edit_approvers`` (ajouté sur la vue purchase.order).
        - Dans ce cas, seules les modifications de ``user_ids`` sont
          autorisées, et uniquement pour le superuser.
        - Les nouveaux approbateurs ajoutés sont notifiés par message.
        """
        from_ui = self.env.context.get('gainde_edit_approvers')

        # Si la modification vient de l'UI de Gainde
        if from_ui:
            # Seul le superuser peut modifier les approbateurs
            if not self.env.is_superuser():
                raise AccessError(_(
                    "Seul l'administrateur peut modifier les approbateurs des étapes d'approbation."
                ))

            # Ne permettre que la modification du champ user_ids
            illegal_keys = set(vals.keys()) - {'user_ids'}
            if illegal_keys:
                raise UserError(_(
                    "Seul le champ des approbateurs peut être modifié sur les étapes d'approbation."
                ))

        # Préparer les anciennes valeurs pour comparer les approbateurs
        notify = from_ui and 'user_ids' in vals
        old_user_ids_map = {}
        if notify:
            for rec in self:
                old_user_ids_map[rec.id] = rec.user_ids

        res = super().write(vals)

        # Notifier les nouveaux approbateurs ajoutés via l'UI
        if notify:
            for rec in self:
                old_users = old_user_ids_map.get(rec.id)
                if old_users is None:
                    continue
                added_users = rec.user_ids - old_users
                if not added_users:
                    continue

                # Récupérer le document lié
                doc = self.env[rec.res_model].browse(rec.res_id)
                doc_name = getattr(doc, 'display_name', False) or getattr(doc, 'name', False) or str(doc.id)

                subject = _("Vous êtes approbateur pour : %s") % doc_name
                body = _(
                    "Bonjour,\n\n"
                    "Vous avez été ajouté comme approbateur pour l'étape \"%(stage)s\" "
                    "du document \"%(doc)s\"."
                ) % {
                    'stage': rec.name,
                    'doc': doc_name,
                }

                partners = added_users.mapped('partner_id')
                if partners:
                    doc.message_post(
                        body=body,
                        subject=subject,
                        partner_ids=partners.ids,
                        message_type='notification',
                    )

        return res

