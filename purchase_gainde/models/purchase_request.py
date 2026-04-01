from odoo import models, fields, api, _, exceptions
from odoo.tools.safe_eval import safe_eval


class PurchaseRequest(models.Model):
    _inherit = "purchase.request"

    has_profile_pr_lines = fields.Boolean(
        string="Has Profile Purchase Request Lines",
        compute="_compute_has_profile_pr_lines",
        store=False,
    )

    # ---------------------------------------------------------------------
    # STATE EXTENSION (selection_add)
    # ---------------------------------------------------------------------
    state = fields.Selection(
        selection_add=[
            ("partially_approved", "Partiellement approuvé"),
            ("n1_approval", "Validation N+1"),
            ("rnd_pending", "R&D"),
            ("rcb_pending", "RCB"),
            ("rcg_pending", "RCG"),
        ],
        # Champ requis dans le core : pour les nouvelles valeurs ajoutées,
        # on doit définir une politique de nettoyage lors de la désinstallation
        # du module. "set default" réinitialise l'état à la valeur par défaut
        # (ex. "draft") si ces valeurs n'existent plus.
        ondelete={
            "partially_approved": "set default",
            "n1_approval": "set default",
            "rnd_pending": "set default",
            "rcb_pending": "set default",
            "rcg_pending": "set default",
        },
        tracking=True,
    )

    is_current_user_coach_request = fields.Boolean(
        string="Is Current User Coach",
        compute="_compute_is_current_user_coach",
        store=False,
    )

    # ---------------------------------------------------------------------
    # ORGANISATION / STRUCTURE
    # ---------------------------------------------------------------------
    department_id = fields.Many2one(
        "hr.department",
        related="requested_by.department_id",
        string="Department",
        store=True,
    )
    picking_type_id = fields.Many2one(required=False)


    # ---------------------------------------------------------------------
    # SPLIT / PARENT–CHILD
    # ---------------------------------------------------------------------
    x_split_parent = fields.Many2one(
        "purchase.request",
        string="Parent Purchase Request",
        ondelete="restrict",
    )
    x_split_children = fields.One2many(
        "purchase.request",
        "x_split_parent",
        string="Child Purchase Requests",
    )

    child_count = fields.Integer(
        compute="_compute_child_count",
        string="Children",
        readonly=True,
    )

    allow_split = fields.Boolean(
        compute="_compute_allow_split",
        store=True,
        string="Allow Split",
    )

    has_selected_for_po = fields.Boolean(
        compute="_compute_has_selected_for_po",
        store=True,
        string="Lines selected for PO",
    )

    @api.model
    def action_open_requests_with_my_approvals(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase_request.purchase_request_form_action"
        )
        has_my_approvals = self.search_count([
            ("current_approval_stage_id.user_ids", "in", self.env.user.id)
        ]) > 0
        if has_my_approvals:
            raw_ctx = action.get("context", {}) or {}
            if isinstance(raw_ctx, str):
                raw_ctx = safe_eval(raw_ctx, {})
            ctx = dict(raw_ctx or {})
            ctx["search_default_my_approvals"] = 1
            action["context"] = ctx
        return action

    def _compute_has_profile_pr_lines(self):
        """True si au moins une ligne est rattachée
        à un des profils actifs de l'utilisateur courant.

        On reflète le domain :
        [('product_id.categ_id.user_profile_id', 'in', profile_ids)]
        où ``profile_ids`` sont les profils actifs de ``env.user``.
        """
        current_user = self.env.user
        # Méthode helper définie dans PurchaseGaindeResUsers
        get_profiles = getattr(current_user, "gainde_get_current_profiles", None)
        current_profile_ids = get_profiles().ids if callable(get_profiles) else []

        for req in self:
            if not current_profile_ids:
                req.has_profile_pr_lines = False
                continue

            req.has_profile_pr_lines = any(
                line.product_id.categ_id.user_profile_id
                and line.product_id.categ_id.user_profile_id.id in current_profile_ids
                for line in req.line_ids
            )
    def action_n2_approved(self, force=False):
            for req in self:
                do_super_approve = True
                if req.state in ("draft") and req.approval_route_id:
                    if len(req.line_ids) <= 0:
                        raise exceptions.UserError(
                            _("La demande d'achat doit contenir au moins une ligne.")
                        )
                    req.generate_approval_route()
                    if req.next_approval_stage_id:
                        req._action_send_to_first_sequence()

                        do_super_approve = False
                        req.write({"state": "n1_approval"})

                elif req.current_approval_stage_id:
                    if req.current_approval_stage_id.sequence == 1:
                        super(PurchaseRequest, req).action_n1_approved()
                        req.action_make_apply_rnd_decision("approved")
                    elif req.current_approval_stage_id.sequence == 3:
                        req.write({"state": "rcg_pending"})
                        req._action_approve()
                    elif req.current_approval_stage_id.sequence == 4:
                        req.write({"state": "to_purchase"})
                        req._action_approve()
                    elif req.current_approval_stage_id.sequence == 5:
                        req.write({"state": "to_purchase"})
                        req._action_approve()
                    else:
                        req._action_approve()
                        do_super_approve = req._is_fully_approved()
                        if do_super_approve:
                            try:
                                req.write({"state": "to_purchase"})
                            except Exception:
                                req.write({"state": "to_approve"})
            return {}


    def action_n2_line_approved(self, force=False):
            
            for req in self:
                
               
                do_super_approve = True
               
           
                
                if req.state in ("draft") and req.approval_route_id:
                   
                    if len(req.line_ids) <= 0:
                        raise exceptions.UserError(
                            _("La demande d'achat doit contenir au moins une ligne.")
                        )
                    req.generate_approval_route()
                    if req.next_approval_stage_id:
                        req._action_send_to_first_sequence()

                        do_super_approve = False
                        for line in req.line_ids:
                            line.write({'state': 'n1_approval'})
                        req.write({"state": "to_approve"})

                elif req.current_approval_stage_id:
                    if req.current_approval_stage_id.sequence == 1:
                        super(PurchaseRequest, req).action_n1_line_approved()
                        req.action_make_apply_rnd_decision("approved")
                    elif req.current_approval_stage_id.sequence == 2:
                        for line in req.line_ids:
                            line.write({'state': 'rnd_pending'})
                    elif req.current_approval_stage_id.sequence == 3:
                        for line in req.line_ids:
                            line.write({'state': 'rcb_pending'})
                    elif req.current_approval_stage_id.sequence == 3:
                        for line in req.line_ids:
                            line.write({'state': 'rcg_pending'})
                        #req.write({"state": "rcg_pending"})
                        req._action_approve()
                    elif req.current_approval_stage_id.sequence == 4:
                        for line in req.line_ids:
                            line.write({'state': 'rcb_pending'})
                        
                        #req.write({"state": "to_purchase"})
                        req._action_approve()
                    elif req.current_approval_stage_id.sequence == 5:
                        for line in req.line_ids:
                            line.write({'state': 'to_purchase'})

                        #req.write({"state": "to_purchase"})
                        req._action_approve()
                    else:
                        req._action_approve()
                        do_super_approve = req._is_fully_approved()
                        if do_super_approve:
                            try:
                                for line in req.line_ids:
                                   line.write({'state': 'to_purchase'})
                                # req.write({"state": "to_purchase"})
                                
                            except Exception:
                                req.write({"state": "to_approve"})
            # raise exceptions.UserError(
            #                 _("La ccljcjl d'achat doit contenir au moins une ligne.")
            #             )
            return {}


    # ---------------------------------------------------------------------
    # COMPUTES
    # ---------------------------------------------------------------------
    @api.depends("x_split_children")
    def _compute_child_count(self):
        for rec in self:
            rec.child_count = len(rec.x_split_children)

    @api.depends(
        "requested_by",
        "requested_by.employee_id",
        "requested_by.employee_id.coach_id")
    def _compute_is_current_user_coach(self):
        current_user = self.env.user
        for rec in self:
            coach_user = (
                rec.requested_by.employee_id.coach_id.user_id
                if rec.requested_by
                and rec.requested_by.employee_id
                and rec.requested_by.employee_id.coach_id
                else False
            )

            rec.is_current_user_coach_request = bool(
                coach_user and coach_user.id == current_user.id 
            )

    @api.depends("x_split_parent")
    def _compute_allow_split(self):
        for rec in self:
            rec.allow_split = not bool(rec.x_split_parent)

    @api.depends("line_ids.selected_for_po")
    def _compute_has_selected_for_po(self):
        for rec in self:
            rec.has_selected_for_po = any(
                rec.line_ids.filtered(lambda l: l.selected_for_po)
            )
    def action_n1_approved(self,force=False):
        # user-visible button / flow hook: block if this PR is already a child
        for rec in self:
            

            if rec.x_split_parent:
                raise exceptions.UserError(_("Cette demande a déjà un parent; le split est désactivé."))
        return self.action_run_split()

    def action_n1_line_approved(self,force=False):
        # user-visible button / flow hook: block if this PR is already a child
        for rec in self:
            

            if rec.x_split_parent:
                raise exceptions.UserError(_("Cette demande a déjà un parent; le split est désactivé."))
        return self.action_run_line_split()
    def action_view_children(self):
        """Return an action opening the child PR(s) for the current PR."""
        action = self.env.ref("purchase_request.purchase_request_form_action").sudo().read()[0]
        children = self.mapped("x_split_children")
        if not children:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Enfants"),
                    "message": _("Cette demande n'a pas d'enfants."),
                    "sticky": False,
                    "type": "info",
                },
            }
        if len(children) == 1:
            action["views"] = [(self.env.ref("purchase_request.view_purchase_request_form").id, "form")]
            action["res_id"] = children.ids[0]
            return action
        action["domain"] = [("id", "in", children.ids)]
        return action
    
    def action_submit(self):
        self.state = "to_approve"    

    def action_n1_approve(self):
        self.state = "n1_approval"

    def action_rnd_approve(self):
        self.state = "rcb_pending"

    def action_rcb_approve(self):
        self.state = "rcg_pending"
  
    def action_rcg_approve(self):
        self.state = "approved"

    def action_send_to_purchase(self):
        self.state = "to_purchase"
    def action_done(self):
        self.state = "done"

    def action_reject(self):
        self.state = "rejected"
    def action_purchase_request_line_make_purchase_order(self):
        for req in self:
            if req.state not in ("approved", "partially_approved"):
                raise exceptions.UserError(
                    _("RFQ can only be created from approved requests.")
                )
        return super().action_purchase_request_line_make_purchase_order()
   
    def _recompute_state_from_lines(self):
        """
        Recompute purchase request state based on line states.

        Rules (synthèse basée sur les lignes):
        - All approved  -> approved
        - All rejected  -> rejected
        - Any mix containing at least one approved OR rejected -> partially_approved
        """

        for request in self:
            lines = request.line_ids
            if not lines:
                continue

            states = set(lines.mapped('state'))

            # All rejected
            if states == {'rejected'}:
                request.state = 'rejected'
                continue

            # All approved
            if states == {'approved'}:
                request.state = 'approved'
                continue

            # Mix (e.g. rejected + pending, approved + pending, approved + rejected, etc.)
            # Dès qu'il y a un état terminal sur au moins une ligne, la demande doit
            # rester sur une synthèse (et ne pas repasser en états workflow type rcb_pending).
            if 'approved' in states or 'rejected' in states:
                request.state = 'partially_approved'
                continue
    def action_run_split(self):
       """
       Perform budget split via budget.analytic lines.

       - Detect poste from product (template or variant)
       - Find matching budgetary centers
       - Resolve center uniquely (department > profile > attitré)
       - Create ONE child PR per center (without copied lines)
       - Copy each line ONCE into its assigned child
       - Archive parent lines
       - Apply analytic_distribution on parent + child
       """

       Budget = self.env["budget.analytic"].sudo()

       for req in self:
        if req.x_split_parent:
            raise exceptions.UserError(
                _("Le split est désactivé : cette demande est déjà un enfant (parent %s).")
                % (req.x_split_parent.display_name)
            )

        center_map = {}  # {center_id: [line, line, ...]}
        log_messages = []

        # ------------------------------------------------------------
        # 1️⃣ ASSIGN EACH LINE TO A UNIQUE CENTER
        # ------------------------------------------------------------
        for line in req.line_ids:

            # Detect poste (template or variant)
            poste = None
            tmpl = line.product_id.product_tmpl_id
            if "post_id" in tmpl._fields:
                poste = tmpl.post_id
            if not poste and "post_id" in line.product_id._fields:
                poste = line.product_id.post_id

            if not poste:
                req.state = "rcg_pending"
                raise exceptions.UserError(_("Poste budgétaire introuvable (ligne %s)") % line.id)

            poste_id = poste.id
            matched_centers = self.env["account.analytic.account"]
            # ✅ budget_line → centers mapping
            bl_center_map = {}   # {bl_id: centers}
            all_centers = self.env["account.analytic.account"]
            # Search budget lines
            for budget in Budget.search([]):
                for bl in budget.budget_line_ids:
                    poste_matched = False
                    centers_for_line = self.env["account.analytic.account"]
                    centers_for_bl = self.env["account.analytic.account"]

                    for fname, fdef in bl._fields.items():
                        if getattr(fdef, "comodel_name", None) != "account.analytic.account":
                            continue
                        if fdef.type not in ("many2one", "many2many"):
                            continue

                        recs = getattr(bl, fname) or self.env["account.analytic.account"]

                        if poste_id in recs.ids and any(
                            a.is_budgetary_poste for a in recs
                        ):
                            poste_matched = True

                        centers_for_line |= recs.filtered(
                            lambda a: a.is_budgetary_center
                        )
                        centers_for_bl |= recs.filtered(lambda a: a.is_budgetary_center)

                    #if poste_matched and centers_for_line:
                    if poste_matched and centers_for_bl:

                        #matched_centers[bl.id] = centers_for_line
                        bl_center_map[bl.id] = centers_for_bl
                        all_centers |= centers_for_bl
                    # if poste_matched:
                    #     matched_centers |= centers_for_line

            #if not matched_centers:
            if not all_centers:

                req.state = "rcg_pending"
                raise exceptions.UserError(
                    _("Aucun centre trouvé pour le poste %s (ligne %s)")
                    % (poste.display_name, line.id)
                )

            # ------------------------------------------------------------
            # 2️⃣ CENTER RESOLUTION (department > profile > attitré)
            # ------------------------------------------------------------
            center = None

            if len(all_centers) == 1:
                #center = matched_centers[0]
                center = all_centers[0]

            else:
                department = req.department_id or None #line.department_id
                dept_centers = self.env["account.analytic.account"]
                if department:
                   dept_budget = Budget.search([("department_id", "=", department.id)], limit=1)

                   if dept_budget:
                    for bl in dept_budget.budget_line_ids:
                         dept_centers |= bl_center_map.get(
                                bl.id, self.env["account.analytic.account"]
                            )
                         #dept_centers |= matched_centers.get(bl.id, self.env["account.analytic.account"])



                # dept_centers = (
                #     matched_centers.filtered(lambda c: c.budget_analytic_id.id == dept_budget.id)
                #     if department
                #     else matched_centers
                # )
                   scope = dept_centers or all_centers

                   #if len(dept_centers) == 1:
                   if len(scope) == 1:
                   
                     center = scope[0] #dept_centers[0]
                else:
                    profile = poste.bp_user_profile
                    profile_centers = (
                        scope.filtered( #dept_centers.filtered(
                            lambda c: c.bc_user_profile == profile
                        )
                        if profile
                        else scope #dept_centers
                    )

                    if len(profile_centers) == 1:
                        center = profile_centers[0]
                    else:
                        attitre_centers = profile_centers.filtered(lambda c: c.bc_user_profile == profile)
                        if len(attitre_centers) == 1:
                            center = attitre_centers[0]
                        else:
                            #req.state = "rcg_pending"
                            raise exceptions.UserError(
                                _("Centre non unique pour poste %s (ligne %s)")
                                % (poste.display_name, line.id)
                            )

            center_map.setdefault(center.id, []).append(line)

        # ------------------------------------------------------------
        # 3️⃣ CREATE CHILD PRs (WITHOUT COPYING LINES)
        # ------------------------------------------------------------
        children = {}
        for center_id in center_map:
            child = req.copy({
                "x_split_parent": req.id,
                "state": 'rnd_pending',
                "line_ids": [(5, 0, 0)],  # 🚨 CRITICAL: prevent duplicate lines
            })
            child.write({"state": 'rnd_pending'})
            #raise exceptions.UserError(_("Creating child PR %s for center %s") % (child.state,child.id))
            children[center_id] = child

        # ------------------------------------------------------------
        # 4️⃣ COPY LINES ONCE + ARCHIVE PARENT
        # ------------------------------------------------------------
        for center_id, lines in center_map.items():
            child = children[center_id]

            for ln in lines:
                ln.write({"state": "archived"})

                ln_child = ln.copy({
                    "request_id": child.id,
                    "state": "to_approve",
                })  

                # ----------------------------------------------------
                # 5️⃣ ANALYTIC DISTRIBUTION (parent + child)
                # ----------------------------------------------------
                poste = None
                tmpl = ln.product_id.product_tmpl_id
                if "post_id" in tmpl._fields:
                    poste = tmpl.post_id
                if not poste and "post_id" in ln.product_id._fields:
                    poste = ln.product_id.post_id

                if poste:
                    key = f"{center_id},{poste.id}"
                    analytic_map = {key: 100}

                    ln_child.write({"analytic_distribution": analytic_map})
                    ln.write({"analytic_distribution": analytic_map})

        # ------------------------------------------------------------
        # 6️⃣ FINALIZE
        # ------------------------------------------------------------
        req.x_split_children = [(6, 0, [c.id for c in children.values()])]
        req.state = "rnd_pending"


    def action_run_line_split(self):
       """
       Perform budget split via budget.analytic lines.

       - Detect poste from product (template or variant)
       - Find matching budgetary centers
       - Resolve center uniquely (department > profile > attitré)
       - Create ONE child PR per center (without copied lines)
       - Copy each line ONCE into its assigned child
       - Archive parent lines
       - Apply analytic_distribution on parent + child
       """

       Budget = self.env["budget.analytic"]

       for req in self:
        if req.x_split_parent:
            raise exceptions.UserError(
                _("Le split est désactivé : cette demande est déjà un enfant (parent %s).")
                % (req.x_split_parent.display_name)
            )

        center_map = {}  # {center_id: [line, line, ...]}
        log_messages = []

        # ------------------------------------------------------------
        # 1️⃣ ASSIGN EACH LINE TO A UNIQUE CENTER
        # ------------------------------------------------------------
        for line in req.line_ids:

            # Detect poste (template or variant)
            poste = None
            tmpl = line.product_id.product_tmpl_id
            if "post_id" in tmpl._fields:
                poste = tmpl.post_id
            if not poste and "post_id" in line.product_id._fields:
                poste = line.product_id.post_id

            if not poste:
                req.state = "rcg_pending"
                raise exceptions.UserError(_("Poste budgétaire introuvable (ligne %s)") % line.id)

            poste_id = poste.id
            matched_centers = self.env["account.analytic.account"]
            # ✅ budget_line → centers mapping
            bl_center_map = {}   # {bl_id: centers}
            all_centers = self.env["account.analytic.account"]
            # Search budget lines
            for budget in Budget.search([]):
                for bl in budget.budget_line_ids:
                    poste_matched = False
                    centers_for_line = self.env["account.analytic.account"]
                    centers_for_bl = self.env["account.analytic.account"]

                    for fname, fdef in bl._fields.items():
                        if getattr(fdef, "comodel_name", None) != "account.analytic.account":
                            continue
                        if fdef.type not in ("many2one", "many2many"):
                            continue

                        recs = getattr(bl, fname) or self.env["account.analytic.account"]

                        if poste_id in recs.ids and any(
                            a.is_budgetary_poste for a in recs
                        ):
                            poste_matched = True

                        centers_for_line |= recs.filtered(
                            lambda a: a.is_budgetary_center
                        )
                        centers_for_bl |= recs.filtered(lambda a: a.is_budgetary_center)

                    #if poste_matched and centers_for_line:
                    if poste_matched and centers_for_bl:

                        #matched_centers[bl.id] = centers_for_line
                        bl_center_map[bl.id] = centers_for_bl
                        all_centers |= centers_for_bl
                    # if poste_matched:
                    #     matched_centers |= centers_for_line

            #if not matched_centers:
            if not all_centers:

                req.state = "rcg_pending"
                raise exceptions.UserError(
                    _("Aucun centre trouvé pour le poste %s (ligne %s)")
                    % (poste.display_name, line.id)
                )

            # ------------------------------------------------------------
            # 2️⃣ CENTER RESOLUTION (department > profile > attitré)
            # ------------------------------------------------------------
            center = None

            if len(all_centers) == 1:
                #center = matched_centers[0]
                center = all_centers[0]

            else:
                department = req.department_id or None #line.department_id
                dept_centers = self.env["account.analytic.account"]
                if department:
                   dept_budget = Budget.search([("department_id", "=", department.id)], limit=1)

                   if dept_budget:
                    for bl in dept_budget.budget_line_ids:
                         dept_centers |= bl_center_map.get(
                                bl.id, self.env["account.analytic.account"]
                            )
                         #dept_centers |= matched_centers.get(bl.id, self.env["account.analytic.account"])



                # dept_centers = (
                #     matched_centers.filtered(lambda c: c.budget_analytic_id.id == dept_budget.id)
                #     if department
                #     else matched_centers
                # )
                scope = dept_centers or all_centers

                #if len(dept_centers) == 1:
                if len(scope) == 1:
                   
                     center = scope[0] #dept_centers[0]
                else:
                    profile = poste.bp_user_profile
                    profile_centers = (
                        scope.filtered( #dept_centers.filtered(
                            lambda c: c.bc_user_profile == profile
                        )
                        if profile
                        else scope #dept_centers
                    )

                    if len(profile_centers) == 1:
                        center = profile_centers[0]
                    else:
                        attitre_centers = profile_centers.filtered(lambda c: c.bc_user_profile == profile)
                        if len(attitre_centers) == 1:
                            center = attitre_centers[0]
                        else:
                            #req.state = "rcg_pending"
                            raise exceptions.UserError(
                                _("Centre non unique pour poste %s (ligne %s)")
                                % (poste.display_name, line.id)
                            )

            center_map.setdefault(center.id, []).append(line)

        # ------------------------------------------------------------
        # 3️⃣ CREATE CHILD PRs (WITHOUT COPYING LINES)
        # ------------------------------------------------------------
        # children = {}
        # for center_id in center_map:
        #     child = req.copy({
        #         "x_split_parent": req.id,
        #         "state": 'rnd_pending',
        #         "line_ids": [(5, 0, 0)],  # 🚨 CRITICAL: prevent duplicate lines
        #     })
        #     child.write({"state": 'rnd_pending'})
        #     #raise exceptions.UserError(_("Creating child PR %s for center %s") % (child.state,child.id))
        #     children[center_id] = child

        # ------------------------------------------------------------
        # 4️⃣ COPY LINES ONCE + ARCHIVE PARENT
        # ------------------------------------------------------------
        for center_id, lines in center_map.items():
                # child = children[center_id]

            for ln in lines:
                #     ln.write({"state": "archived"})

                #     ln_child = ln.copy({
                #         "request_id": child.id,
                #         "state": "to_approve",
                #     })  

                # ----------------------------------------------------
                # 5️⃣ ANALYTIC DISTRIBUTION (parent + child)
                # ----------------------------------------------------
                poste = None
                tmpl = ln.product_id.product_tmpl_id
                if "post_id" in tmpl._fields:
                    poste = tmpl.post_id
                if not poste and "post_id" in ln.product_id._fields:
                    poste = ln.product_id.post_id

                if poste:
                    key = f"{center_id},{poste.id}"
                    analytic_map = {key: 100}

                    #ln_child.write({"analytic_distribution": analytic_map})
                    ln.write({"analytic_distribution": analytic_map,'state': "rcg_pending"})
                    

        # ------------------------------------------------------------
        # 6️⃣ FINALIZE
        # ------------------------------------------------------------
        #req.x_split_children = [(6, 0, [c.id for c in children.values()])]
        #req.state = "rnd_pending"


