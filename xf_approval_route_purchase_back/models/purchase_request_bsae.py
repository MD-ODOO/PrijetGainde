from odoo import models, fields, api, _, exceptions
from odoo.exceptions import UserError, AccessError
import logging

_logger = logging.getLogger(__name__)


class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _inherit = ['purchase.request', 'approval.route.document']

    approval_route_id = fields.Many2one(
        comodel_name="approval.route",
        readonly=True,
    )

    all_used_products = fields.Many2many(
        comodel_name='product.product',
        compute="_compute_all_used_products",
        string='All Used Products',
    )

    all_used_analytic_accounts = fields.Many2many(
        comodel_name='account.analytic.account',
        compute="_compute_all_used_analytic_accounts",
        string='All Used Analytic Accounts',
    )

    approval_stage_name = fields.Char(
        string="Approval Stage",
        compute="_compute_approval_stage_name",
        readonly=True
    )

    # ======================================================
    # COMPUTES
    # ======================================================

    @api.depends("line_ids.product_id")
    def _compute_all_used_products(self):
        for req in self:
            req.all_used_products = req.line_ids.mapped("product_id")

    @api.depends("line_ids.analytic_distribution")
    def _compute_all_used_analytic_accounts(self):
        for req in self:
            analytic_ids = set()
            for line in req.line_ids:
                for key in (line.analytic_distribution or {}):
                    for part in key.split(","):
                        if part.isdigit():
                            analytic_ids.add(int(part))
            req.all_used_analytic_accounts = list(analytic_ids)

    @api.depends("current_approval_stage_id")
    def _compute_approval_stage_name(self):
        for rec in self:
            rec.approval_stage_name = (
                rec.current_approval_stage_id.name
                if rec.current_approval_stage_id else False
            )

    # ======================================================
    # ANALYTIC / CENTER HELPERS
    # ======================================================

    def _get_budgetary_center(self):
        self.ensure_one()
        AA = self.env['account.analytic.account']

        for ln in self.line_ids:
            dist = ln.analytic_distribution or {}
            if not dist:
                continue

            key = next(iter(dist.keys()), None)
            if not key:
                continue

            try:
                center_id = int(str(key).split(',')[0])
            except Exception:
                continue

            center = AA.browse(center_id).with_context(active_test=False)
            if center.exists():
                return center

        return AA.browse(False)

    def get_rc_user_ids_from_budget_center(self):
        self.ensure_one()
        center = self._get_budgetary_center()

        if not center:
            _logger.debug("PR %s: aucun centre budgétaire trouvé.", self.id)
            return []

        profile = getattr(center, "bc_user_profile", False)
        if profile and hasattr(profile, "access_user_ids"):
            return list(set(profile.access_user_ids.ids))

        return []

    def get_rc_partner_ids_from_budget_center(self):
        self.ensure_one()
        return self.get_rc_user_ids_from_budget_center()

    # ======================================================
    # APPROVAL FLOW
    # ======================================================

    def action_n2_approved(self, force=False):
        for req in self:
            if req.state == "draft" and req.approval_route_id:
                if not req.line_ids:
                    raise UserError(_("La demande d'achat doit contenir au moins une ligne."))

                req.generate_approval_route()

                if req.next_approval_stage_id:
                    req._action_send_to_approve()
                    req.write({'state': 'n1_approval'})
                    continue

            if not req.current_approval_stage_id:
                continue

            seq = req.current_approval_stage_id.sequence

            if seq == 1:
                super(PurchaseRequest, req).action_n1_approved()
                req.action_make_apply_rnd_decision('approved')

            elif seq == 3:
                req.write({"state": "rcg_pending"})
                req._action_approve()

            elif seq == 4:
                req.write({"state": "to_purchase"})
                req._action_approve()

            elif seq == 5:
                req.write({"state": "rcb_approval"})
                req._action_approve()

            else:
                req._action_approve()
                if req._is_fully_approved():
                    req.write({"state": "approved"})

        return True

    def _approval_allowed(self):
        return True

    # ======================================================
    # BUTTONS
    # ======================================================

    def button_to_approve(self):
        for req in self:
            if req.state != 'draft':
                continue

            if req.approval_route_id:
                req.generate_approval_route()
                if req.next_approval_stage_id:
                    req._action_send_to_approve()
                    req.write({"state": "n1_approval"})
                    continue

            super(PurchaseRequest, req).button_to_approve()

        return True

    def button_draft(self):
        self._clear_approval_stages()
        return super(PurchaseRequest, self).button_draft()

    # ======================================================
    # DEFAULT ROUTE
    # ======================================================

    def _get_default_approval_route_for_company(self, company):
        route = self.env.ref(
            "xf_approval_route_purchase.xf_route_purchase_request_default",
            raise_if_not_found=False,
        )
        if route and (not route.company_id or route.company_id == company):
            return route

        return self.env["approval.route"].search(
            [("model", "=", "purchase.request"), ("company_id", "in", [company.id, False])],
            limit=1,
        )

    @api.model_create_multi
    def create(self, vals_list):
        new_vals_list = []
        for vals in vals_list:
            v = dict(vals)
            if "approval_route_id" not in v:
                company = self.env["res.company"].browse(
                    v.get("company_id", self.env.company.id)
                )
                route = self._get_default_approval_route_for_company(company)
                if route:
                    v["approval_route_id"] = route.id
            new_vals_list.append(v)
        return super(PurchaseRequest, self).create(new_vals_list)

    def write(self, vals):
        if "company_id" in vals and "approval_route_id" not in vals:
            for rec in self:
                if not rec.approval_route_id:
                    company = self.env["res.company"].browse(vals["company_id"])
                    route = self._get_default_approval_route_for_company(company)
                    if route:
                        super(PurchaseRequest, rec).write({"approval_route_id": route.id})
        return super(PurchaseRequest, self).write(vals)

    # ======================================================
    # APPROVE DISPATCH
    # ======================================================

    def _action_approve(self):
        stage_n1 = self.env.ref(
            "xf_approval_route_purchase.xf_stage_n1_approval",
            raise_if_not_found=False,
        )
        res = None
        for rec in self:
            if stage_n1 and rec.current_approval_stage_id == stage_n1:
                res = rec.action_n1_approved()
            else:
                parent = super(PurchaseRequest, rec)
                method = getattr(parent, "_action_approve", None)
                if method:
                    res = method()
        return res
