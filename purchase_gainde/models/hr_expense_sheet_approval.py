# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import AccessError, UserError
from odoo.addons.xf_approval_route_base.models import selection


class HrExpenseSheet(models.Model):
    _name = 'hr.expense.sheet'
    _inherit = ['hr.expense.sheet', 'approval.route.document']

    use_approval_route = fields.Selection(
        string="Use Approval Route",
        related='company_id.use_approval_route_expense',
    )
    approval_route_id = fields.Many2one(
        readonly=True,
    )
    is_admin_ui = fields.Boolean(
        string='Is Admin UI',
        compute='_compute_is_admin_ui',
        compute_sudo=True,
    )
    all_used_analytic_accounts = fields.Many2many(
        string='All Used Analytic Accounts',
        comodel_name='account.analytic.account',
        compute='_compute_all_used_analytic_accounts',
    )

    @api.depends('expense_line_ids.analytic_distribution')
    def _compute_all_used_analytic_accounts(self):
        for sheet in self:
            analytic_account_ids = []
            for line in sheet.expense_line_ids:
                if line.analytic_distribution:
                    aa_keys = line.analytic_distribution.keys()
                    for aa_key in aa_keys:
                        aa_ids = aa_key.split(',')
                        analytic_account_ids += list(map(int, aa_ids))
            sheet.all_used_analytic_accounts = list(set(analytic_account_ids))

    def _compute_is_admin_ui(self):
        is_admin = self.env.user.has_group('base.group_system') or self.env.is_superuser()
        for sheet in self:
            sheet.is_admin_ui = is_admin

    def action_submit_sheet(self):
        for sheet in self:
            if sheet.state == 'draft':
                sheet._gainde_check_has_attachments_before_submit()
            if sheet.state == 'draft' and sheet.use_approval_route != 'no' and sheet.approval_route_id:
                # Generate approval workflow and send expense sheet to approve
                sheet.generate_approval_route()
                sheet._gainde_apply_rm_da_validation_order()
                
                if sheet.next_approval_stage_id:
                    # If approval route was generated and there is next approver mark the sheet as submitted
                    sheet.write({'state': 'submit'})
                    # And send request to approve
                    sheet._action_send_to_approve()
                else:
                    # If there are no approvers, do default behaviour
                    super(HrExpenseSheet, sheet).action_submit_sheet()
            else:
                # Do default behaviour if approval route is not set
                # or approval functionality is disabled
                super(HrExpenseSheet, sheet).action_submit_sheet()

    def _gainde_check_has_attachments_before_submit(self):
        """Bloque la soumission si aucun justificatif n'est présent.

        On accepte une pièce jointe soit sur la feuille (hr.expense.sheet),
        soit sur au moins une ligne (hr.expense).
        """

        self.ensure_one()

        Attachment = self.env["ir.attachment"].sudo()
        line_ids = self.expense_line_ids.ids

        domain_sheet = [
            ("res_model", "=", self._name),
            ("res_id", "=", self.id),
        ]
        if line_ids:
            domain = [
                "|",
                "&",
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                "&",
                ("res_model", "=", "hr.expense"),
                ("res_id", "in", line_ids),
            ]
        else:
            domain = domain_sheet

        if not Attachment.search_count(domain):
            raise UserError(
                _(
                    "Veuillez ajouter au moins une pièce jointe (justificatif) avant de soumettre la note de frais."
                )
            )

    @api.depends_context('uid')
    @api.depends('employee_id', 'approval_route_id', 'current_approval_stage_id')
    def _compute_can_approve(self):
        for sheet in self:
            if sheet.use_approval_route != 'no' and sheet.approval_route_id and sheet.is_under_approval:
                approvers = sheet.current_approval_stage_id.user_ids
                names = approvers.mapped('name')
                reason = _('This %s must be approved/refused by %s') % (self._description, ' or '.join(names))
                sheet.can_approve = sheet.is_current_approver
                sheet.cannot_approve_reason = reason
            else:
                super(HrExpenseSheet, sheet)._compute_can_approve()

    def _check_can_approve(self):
        if self.use_approval_route != 'no' and self.approval_route_id and self.is_under_approval:
            # If dynamic approval workflow is enabled
            if not self._is_fully_approved():
                approvers = self.current_approval_stage_id.user_ids
                names = approvers.mapped('name')
                # Check is the current user is approver for the current stage
                if self.env.user not in approvers and not self.env.is_superuser():
                    raise AccessError(_('This %s must be approved by %s') % (self._description, ' or '.join(names)))
        else:
            return super(HrExpenseSheet, self)._check_can_approve()

    def action_approve_expense_sheets(self):
        # Gestion par feuille pour pouvoir déclencher la notification uniquement
        # quand la dernière approbation (DA) finalise totalement la note.
        result = True

        for sheet in self:
            if sheet.use_approval_route != 'no' and sheet.approval_route_id and sheet.is_under_approval:
                was_da_stage = bool(
                    sheet.current_approval_stage_id
                    and sheet.current_approval_stage_id.name == "DA"
                )

                sheet._action_approve()

                if sheet._is_fully_approved():
                    result = super(HrExpenseSheet, sheet).action_approve_expense_sheets()
                    if was_da_stage:
                        sheet._gainde_notify_compta_new_approved_sheet()
            else:
                # Do default behaviour if approval route is not set
                result = super(HrExpenseSheet, sheet).action_approve_expense_sheets()

        return result

    def action_reset_expense_sheets(self):
        """
        Clear approval stages and reset expense reports
        :return:
        """
        self._clear_approval_stages()
        return super(HrExpenseSheet, self).action_reset_expense_sheets()

    def _gainde_apply_rm_da_validation_order(self):
        """Force l'ordre de validation des notes de frais.

        Règle demandée:
        - Démarrer par "RM" (Responsable mission)
        - Puis "DA"
        - Pas d'étape "MENTOR" ni "RCG"

        Les approvers sont résolus via le profile_type (rm/da) et, à défaut,
        via le modèle approval.role (nom RM/DA).
        """

        Stage = self.env["approval.route.document.stage"].sudo()

        for sheet in self:
            stages = sheet.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
            if not stages:
                continue

            # On veut strictement RM -> DA, donc on supprime toute autre étape existante.
            # (Historique: MENTOR / RCG / autres étapes de la route initiale)
            to_remove = stages.filtered(lambda s: s.name not in {"RM", "DA"})
            if to_remove:
                to_remove.unlink()
                stages = sheet.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))

            # Résoudre les approvers RM / DA
            rm_ids = sheet._gainde_get_approver_user_ids("RM", "rm") or []
            da_ids = sheet._gainde_get_approver_user_ids("DA", "da") or []
            if not rm_ids:
                raise AccessError(
                    _(
                        "Please configure Responsable mission (RM) approvers (profile type 'rm' or approval role 'RM') before submitting."
                    )
                )
            if not da_ids:
                raise AccessError(
                    _(
                        "Please configure DA approvers (profile type 'da' or approval role 'DA') before submitting."
                    )
                )

            # Récupérer ou créer les étapes RM / DA
            rm_stage = stages.filtered(lambda s: s.name == "RM")[:1]
            if not rm_stage:
                rm_stage = Stage.create(
                    {
                        "res_model": sheet._name,
                        "res_id": sheet.id,
                        "sequence": 1,
                        "name": "RM",
                        "user_ids": [Command.set(rm_ids)],
                        "approval_type": selection.APPROVAL_TYPE_ONE,
                        "state": selection.APPROVAL_STATE_TO_APPROVE,
                    }
                )
            else:
                rm_stage.write({"user_ids": [Command.set(rm_ids)]})

            da_stage = stages.filtered(lambda s: s.name == "DA")[:1]
            if not da_stage:
                da_stage = Stage.create(
                    {
                        "res_model": sheet._name,
                        "res_id": sheet.id,
                        "sequence": 2,
                        "name": "DA",
                        "user_ids": [Command.set(da_ids)],
                        "approval_type": selection.APPROVAL_TYPE_ONE,
                        "state": selection.APPROVAL_STATE_TO_APPROVE,
                    }
                )
            else:
                da_stage.write({"user_ids": [Command.set(da_ids)]})

            # Normaliser les séquences: RM=1, DA=2, puis le reste
            rm_stage.sequence = 1
            da_stage.sequence = 2

    def _gainde_notify_compta_new_approved_sheet(self):
        """Notifier les utilisateurs du profil compta qu'une note approuvée est à traiter."""

        self.ensure_one()

        user_ids = self._gainde_get_profile_user_ids_by_type("compta") or []
        partners = self.env["res.users"].sudo().browse(user_ids).mapped("partner_id")
        partners = partners.filtered(lambda p: p and p.active)
        if not partners:
            return

        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        sheet_url = ""
        if base_url:
            sheet_url = f"{base_url}/web#id={self.id}&model={self._name}&view_type=form"

        doc_url = self.env["ir.config_parameter"].sudo().get_param(
            "purchase_gainde.expense_compta_doc_url"
        )

        body_parts = [
            _("Une nouvelle note de frais a été approuvée et est à prendre en compte par la comptabilité."),
            _("Note de frais: %s") % (self.display_name or ""),
        ]
        if sheet_url:
            body_parts.append(_("Lien: %s") % sheet_url)
        if doc_url:
            body_parts.append(_("Documentation: %s") % doc_url)

        self.message_post(
            body="<br/>".join(body_parts),
            partner_ids=partners.ids,
            subtype_xmlid="mail.mt_comment",
        )

    def _gainde_get_profile_user_ids_by_type(self, profile_type):
        """Retourne les users rattachés à un profile_type donné."""
        Profile = self.env["user.profiles"]
        types = list({profile_type, (profile_type or "").lower(), (profile_type or "").upper()})
        profiles = Profile.search([("profile_type", "in", types)])
        user_ids = set()
        for profile in profiles:
            user_ids.update(profile.access_user_ids.ids)
            enabled_lines = profile.access_line_ids.filtered(
                lambda l: getattr(l, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
        return list(user_ids)

    def _gainde_get_approver_user_ids(self, role_name, profile_type):
        """Retourne les approvers via profile_type, sinon via approval.role."""
        user_ids = set(self._gainde_get_profile_user_ids_by_type(profile_type) or [])
        if user_ids:
            return list(user_ids)

        role_domain = [("name", "=", role_name)]
        if self.company_id:
            role_domain = ["|", ("company_id", "=", self.company_id.id), ("company_id", "=", False)] + role_domain
        role = self.env["approval.role"].sudo().search(role_domain, limit=1)
        if role:
            user_ids.update(role.user_ids.ids)
        return list(user_ids)


