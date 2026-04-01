# -*- coding: utf-8 -*-
from odoo import models, fields, api, _, Command
from odoo.exceptions import AccessError
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

    def action_submit_sheet(self):
        for sheet in self:
            if sheet.state == 'draft' and sheet.use_approval_route != 'no' and sheet.approval_route_id:
                # Generate approval workflow and send expense sheet to approve
                sheet.generate_approval_route()
                sheet._gainde_set_rcg_daf_approvers()
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
        if self.use_approval_route != 'no' and self.approval_route_id and self.is_under_approval:
            self._action_approve()
            if self._is_fully_approved():
                return super(HrExpenseSheet, self).action_approve_expense_sheets()
        else:
            # Do default behaviour if approval route is not set
            return super(HrExpenseSheet, self).action_approve_expense_sheets()

    def action_reset_expense_sheets(self):
        """
        Clear approval stages and reset expense reports
        :return:
        """
        self._clear_approval_stages()
        return super(HrExpenseSheet, self).action_reset_expense_sheets()

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

    def _gainde_set_rcg_daf_approvers(self):
        for sheet in self:
            stages = sheet.approval_route_stage_ids
            if not stages:
                continue
            rcg_ids = sheet._gainde_get_profile_user_ids_by_type("rcg") or []
            daf_ids = sheet._gainde_get_profile_user_ids_by_type("daf") or []

            for stage in stages:
                if stage.name == "RCG" and rcg_ids:
                    stage.sudo().write({"user_ids": [Command.set(rcg_ids)]})
                elif stage.name == "DAF" and daf_ids:
                    stage.sudo().write({"user_ids": [Command.set(daf_ids)]})

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

    def _gainde_insert_rcg_daf_stages(self):
        """Insère les étapes RCG puis DAF après l'étape manager (première étape)."""
        for sheet in self:
            stages = sheet.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
            if not stages:
                continue

            existing_names = set(stages.mapped("name"))
            to_add = []
            if "RCG" not in existing_names:
                to_add.append(("RCG", "rcg"))
            if "DAF" not in existing_names:
                to_add.append(("DAF", "daf"))

            if not to_add:
                continue

            manager_stage = stages[0]
            insert_after_seq = manager_stage.sequence
            shift = len(to_add)

            # Décaler les séquences existantes après l'étape manager
            for st in stages.filtered(lambda s: s.sequence > insert_after_seq):
                st.sequence = st.sequence + shift

            # Créer les nouvelles étapes
            next_seq = insert_after_seq + 1
            for name, profile_type in to_add:
                user_ids = sheet._gainde_get_approver_user_ids(name, profile_type)
                sheet.env["approval.route.document.stage"].create({
                    "res_model": sheet._name,
                    "res_id": sheet.id,
                    "sequence": next_seq,
                    "name": name,
                    "user_ids": [Command.set(user_ids)],
                    "approval_type": selection.APPROVAL_TYPE_ONE,
                    "state": selection.APPROVAL_STATE_TO_APPROVE,
                })
                next_seq += 1
