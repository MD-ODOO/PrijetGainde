# Copyright 2018-2019 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models, exceptions
from odoo.exceptions import UserError

_STATES = [
    ("draft", "Brouillon"),
    ("to_approve", "À approuver"),
    ("partially_approved", "Partiellement approuvé"),
    ("n1_approval", "Validation N+1"),
    ("rnd_pending", "RND"),
    ("rcb_pending", "RCB"),
    ("rcg_pending", "RCG"),
    ("rcb_final_approval", "Approbation finale RCB"),
    ("approved", "Approuvé"),
    ("to_purchase", "Traitement Achats"),
    ("in_progress", "En cours"),
    ("done", "Terminé"),
    ("rejected", "Rejeté"),
]


class PurchaseRequestLine(models.Model):
    _inherit = "purchase.request.line"
   
    # Indique si l'utilisateur courant est approbateur sur la demande parente
   

    state = fields.Selection(
        selection=_STATES,
        string="Statut",
        # Comme pour purchase.request.state, on définit une politique
        # de nettoyage pour chaque valeur en cas de désinstallation
        # du module, en remettant l'état à sa valeur par défaut.
        ondelete={
            "draft": "set default",
            "to_approve": "set default",
            "partially_approved": "set default",
            "n1_approval": "set default",
            "rnd_pending": "set default",
            "rcb_pending": "set default",
            "rcg_pending": "set default",
            "rcb_final_approval": "set default",
            "approved": "set default",
            "to_purchase": "set default",
            "in_progress": "set default",
            "done": "set default",
            "rejected": "set default",
        },
        tracking=True,
    )
    is_current_user_coach = fields.Boolean(
        string="Is Current User Coach",
        compute="_compute_is_current_user_coach",
        store=False,
    )
    is_current_user_coach_checker = fields.Boolean(
        string="Is Current User Coach Checker",
        compute="_compute_is_current_user_coach_checker",
        store=False,
    )
    is_admin_ui = fields.Boolean(
        string="Is Admin UI",
        compute="_compute_is_admin_ui",
        store=False,
    )
    can_edit_estimated_cost = fields.Boolean(
        string="Can Edit Estimated Cost",
        compute="_compute_gainde_user_profile_flags",
        store=False,
    )
    can_edit_analytic_distribution = fields.Boolean(
        string="Can Edit Analytic Distribution",
        compute="_compute_gainde_user_profile_flags",
        store=False,
    )

    @api.depends(
        "request_id.requested_by",
        "request_id.requested_by.employee_id",
        "request_id.requested_by.employee_id.coach_id",
        'state'
    )
    def _compute_is_current_user_coach(self):
        current_user = self.env.user
        for line in self:
            coach_user = (
                line.request_id.requested_by.employee_id.coach_id.user_id
                if line.request_id
                and line.request_id.requested_by
                and line.request_id.requested_by.employee_id
                and line.request_id.requested_by.employee_id.coach_id
                else False
            )

            line.is_current_user_coach = bool(
                coach_user and coach_user.id == current_user.id and line.state == 'n1_approval'
            )
    @api.depends(
        "request_id.requested_by",
        "request_id.requested_by.employee_id",
        "request_id.requested_by.employee_id.coach_id",
    )
    def _compute_is_current_user_coach_checker(self):
        current_user = self.env.user
        for line in self:
            coach_user = (
                line.request_id.requested_by.employee_id.coach_id.user_id
                if line.request_id
                and line.request_id.requested_by
                and line.request_id.requested_by.employee_id
                and line.request_id.requested_by.employee_id.coach_id
                else False
            )

            line.is_current_user_coach_checker = bool(
                coach_user and coach_user.id == current_user.id
            )

    def _compute_is_admin_ui(self):
        is_admin = self.env.user.has_group('base.group_system') or self.env.is_superuser()
        for line in self:
            line.is_admin_ui = is_admin

    @api.depends("state")
    def _compute_gainde_user_profile_flags(self):
        current_user = self.env.user
        is_admin = current_user.has_group("base.group_system") or self.env.is_superuser()

        if is_admin:
            for line in self:
                line.can_edit_estimated_cost = True
                line.can_edit_analytic_distribution = True
            return

        # profils actifs via access_profile_line_ids
        lines = current_user.sudo().access_profile_line_ids.filtered(
            lambda l: getattr(l, "active", True) and getattr(l, "access_is_enabled", True)
        )
        profiles = lines.mapped("access_profile_id")
        # fallback sur profils direct si présents
        direct_profiles = getattr(current_user, "access_profile_ids", self.env["user.profiles"])
        if direct_profiles:
            profiles |= direct_profiles
        types = set((profiles.mapped("profile_type")) or [])
        has_ra = "ra" in types
        has_assistante_ra = "assistante_ra" in types
        has_rcg = "rcg" in types
        for line in self:
            line.can_edit_estimated_cost = has_ra or has_assistante_ra
            line.can_edit_analytic_distribution = has_rcg



    
    #     requested_qty = fields.Float(string="Requested Qty")
    qty_to_purchase = fields.Float(string="Qty to Purchase")
    preferred_vendor_id = fields.Many2one('res.partner', string="Preferred Vendor")
    estimated_price = fields.Monetary(string="Estimated Unit Price")
    estimated_total = fields.Monetary(string="Estimated Line Total", compute="_compute_estimated_total", store=True)
    selected_for_po = fields.Boolean(
        string="Selected for PO", default=False
    )
    selectable_for_po = fields.Boolean(
        compute="_compute_selectable_for_po",
        string="Selectable for PO",
    )

    rejection_reason = fields.Text(string="Motif du rejet")
    #@api.constrains('estimated_cost')
    #def _check_estimated_cost_edit(self):
    #  for line in self:
    #    if line.request_id.state != 'approved' and line.state not in ('approved','rejected'):
    #        raise ValidationError(_("Estimated cost can only be modified when approved."))


 
    # ACTION: APPROVE SELECTED LINES
    # ------------------------------------------------------------
    def action_approve_lines(self):
        for line in self:
            #if not line.request_id:
            #    continue

            #if line.request_id.state not in ("draft", "to_approve"):
            #    raise UserError(
            #        _("Only Draft or To Approve requests can be approved.")
            #    )

            line.state = "approved"
        # Vérifie la demande après changement d'état des lignes
        self._check_request_after_line_state_change()

    # ------------------------------------------------------------
    # ACTION: REJECT SELECTED LINES
    # ------------------------------------------------------------
    def action_reject_lines(self):
        for line in self:
            # if not line.request_id:
            #     continue

            # if line.request_id.state in ("done", "cancel"):
            #     raise UserError(
            #         _("You cannot reject a completed or cancelled request.")
            #     )

            line.state = "rejected"
            message_body = _(
                    """
                Dear colleagues,
                Your approbation request line  %s "%s" has been rejected.
                """
                ) % (self._description, line.display_name)
            partner = (
                    self.request_id.requested_by.partner_id
                    if self.request_id.requested_by.partner_id else False
                )

            if partner is not False:
                    line.message_post(body=message_body, partner_ids=[partner.id])
                    
            # Vérifie la demande après changement d'état des lignes
            self._check_request_after_line_state_change()

    def _check_request_after_line_state_change(self):
        """Met à jour l'état de la demande en fonction de ses lignes.

        - Utilise _recompute_state_from_lines() pour positionner
          "approved" / "rejected" / "partially_approved".
        - Si toutes les lignes sont soit approuvées soit rejetées,
          déclenche ensuite le saut à l'étape 3 (action_jump_to_stage_3),
          si disponible sur le modèle.
        """
        requests = self.mapped("request_id")
        for request in requests:
            if not request:
                continue
            lines = request.line_ids
            if not lines:
                continue
            # Toujours recalcule l'état de la demande selon les lignes
            # (approved / rejected / partially_approved)
            recompute = getattr(request, "_recompute_state_from_lines", None)
            if callable(recompute):
                recompute()

            # Si toutes les lignes sont dans un état terminal (approved/rejected),
            # on peut faire avancer le workflow via action_jump_to_stage_3, si présent.
            if all(l.state in ("approved", "rejected") for l in lines):
                action = getattr(request, "action_jump_to_stage_3", None)
                if callable(action):
                    action()

                # action_jump_to_stage_3 peut repositionner request.state sur un état
                # de workflow (ex: rcb_pending). On ré-applique la synthèse.
                recompute = getattr(request.sudo(), "_recompute_state_from_lines", None)
                if callable(recompute):
                    recompute()

                # else:
                #     _logger.warning(
                #         "_action_approve non trouvée sur purchase.request id=%s",
                #         request.id,
                #     )

    @api.depends('estimated_price','qty_to_purchase')
    def _compute_estimated_total(self):
        for rec in self:
            rec.estimated_total = (rec.estimated_price or 0) * (rec.qty_to_purchase or 0)
    # def action_submit(self):
    #     self.state = "to_approve"    

    @api.depends(
        "purchase_request_allocation_ids",
        "purchase_request_allocation_ids.stock_move_id.state",
        "purchase_request_allocation_ids.stock_move_id",
        "purchase_request_allocation_ids.purchase_line_id",
        "purchase_request_allocation_ids.purchase_line_id.state",
        "request_id.state",
        "product_qty",
    )
    def _compute_qty_to_buy(self):
        for pr in self:
            qty_to_buy = sum(pr.mapped("product_qty")) - sum(pr.mapped("qty_done"))
            pr.qty_to_buy = qty_to_buy > 0.0
            pr.pending_qty_to_receive = qty_to_buy

    @api.depends(
        "purchase_request_allocation_ids",
        "purchase_request_allocation_ids.stock_move_id.state",
        "purchase_request_allocation_ids.stock_move_id",
        "purchase_request_allocation_ids.purchase_line_id.state",
        "purchase_request_allocation_ids.purchase_line_id",
    )
    def _compute_qty(self):
        for request in self:
            done_qty = sum(
                request.purchase_request_allocation_ids.mapped("allocated_product_qty")
            )
            open_qty = sum(
                request.purchase_request_allocation_ids.mapped("open_product_qty")
            )
            request.qty_done = done_qty
            request.qty_in_progress = open_qty

    @api.depends(
        "purchase_request_allocation_ids",
        "purchase_request_allocation_ids.stock_move_id.state",
        "purchase_request_allocation_ids.stock_move_id",
        "purchase_request_allocation_ids.purchase_line_id.order_id.state",
        "purchase_request_allocation_ids.purchase_line_id",
    )
    def _compute_qty_cancelled(self):
        for request in self:
            if request.product_id.type != "service":
                qty_cancelled = sum(
                    request.mapped("purchase_request_allocation_ids.stock_move_id")
                    .filtered(lambda sm: sm.state == "cancel")
                    .mapped("product_qty")
                )
            else:
                qty_cancelled = sum(
                    request.mapped("purchase_request_allocation_ids.purchase_line_id")
                    .filtered(lambda sm: sm.state == "cancel")
                    .mapped("product_qty")
                )
                # done this way as i cannot track what was received before
                # cancelled the purchase order
                qty_cancelled -= request.qty_done
            if request.product_uom_id:
                request.qty_cancelled = (
                    max(
                        0,
                        request.product_id.uom_id._compute_quantity(
                            qty_cancelled, request.product_uom_id
                        ),
                    )
                    if request.purchase_request_allocation_ids
                    else 0
                )
            else:
                request.qty_cancelled = qty_cancelled

    @api.depends(
        "purchase_lines",
        "request_id.state",
    )
    def _compute_is_editable(self):
        for rec in self:
            if rec.request_id.state in (
                "to_approve",
                "approved",
                "rejected",
                "in_progress",
                "done",
            ):
                rec.is_editable = False
            else:
                rec.is_editable = True
        for rec in self.filtered(lambda p: p.purchase_lines):
            rec.is_editable = False

    @api.depends("product_id", "product_id.seller_ids")
    def _compute_supplier_id(self):
        for rec in self:
            sellers = rec.product_id.seller_ids.filtered(
                lambda si, rec=rec: not si.company_id or si.company_id == rec.company_id
            )
            rec.supplier_id = sellers[0].partner_id if sellers else False

    @api.onchange("product_id")
    def onchange_product_id(self):
        if self.product_id:
            name = self.product_id.name
            if self.product_id.code:
                name = f"[{self.product_id.code}] {name}"
            if self.product_id.description_purchase:
                name += "\n" + self.product_id.description_purchase
            self.product_uom_id = self.product_id.uom_id.id
            self.product_qty = 1
            self.name = name

    def do_cancel(self):
        """Actions to perform when cancelling a purchase request line."""
        self.write({"cancelled": True})

    def do_uncancel(self):
        """Actions to perform when uncancelling a purchase request line."""
        self.write({"rejected": False})

    # def write(self, vals):
    #     res = super().write(vals)
    #     if vals.get("rejected"):
    #         requests = self.mapped("request_id")
    #         requests.check_auto_reject()
    #     return res
    def write(self, vals):
        res = super().write(vals)

        if 'state' in vals:
            requests = self.mapped('request_id')
            requests._recompute_state_from_lines()

        return res

    def _compute_purchased_qty(self):
        for rec in self:
            rec.purchased_qty = 0.0
            for line in rec.purchase_lines.filtered(lambda x: x.state != "cancel"):
                if rec.product_uom_id and line.product_uom != rec.product_uom_id:
                    rec.purchased_qty += line.product_uom._compute_quantity(
                        line.product_qty, rec.product_uom_id
                    )
                else:
                    rec.purchased_qty += line.product_qty

    @api.depends("purchase_lines.state", "purchase_lines.order_id.state")
    def _compute_purchase_state(self):
        for rec in self:
            temp_purchase_state = False
            if rec.purchase_lines:
                if any(po_line.state == "done" for po_line in rec.purchase_lines):
                    temp_purchase_state = "done"
                elif all(po_line.state == "cancel" for po_line in rec.purchase_lines):
                    temp_purchase_state = "cancel"
                elif any(po_line.state == "purchase" for po_line in rec.purchase_lines):
                    temp_purchase_state = "purchase"
                elif any(
                    po_line.state == "to approve" for po_line in rec.purchase_lines
                ):
                    temp_purchase_state = "to approve"
                elif any(po_line.state == "sent" for po_line in rec.purchase_lines):
                    temp_purchase_state = "sent"
                elif all(
                    po_line.state in ("draft", "cancel")
                    for po_line in rec.purchase_lines
                ):
                    temp_purchase_state = "draft"
            rec.purchase_state = temp_purchase_state

    @api.model
    def _get_supplier_min_qty(self, product, partner_id=False):
        seller_min_qty = 0.0
        if partner_id:
            seller = product.seller_ids.filtered(
                lambda r: r.partner_id == partner_id
            ).sorted(key=lambda r: r.min_qty)
        else:
            seller = product.seller_ids.sorted(key=lambda r: r.min_qty)
        if seller:
            seller_min_qty = seller[0].min_qty
        return seller_min_qty

    @api.model
    def _calc_new_qty(self, request_line, po_line=None, new_pr_line=False):
        purchase_uom = po_line.product_uom or request_line.product_id.uom_po_id
        # TODO: Not implemented yet.
        #  Make sure we use the minimum quantity of the partner corresponding
        #  to the PO. This does not apply in case of dropshipping
        supplierinfo_min_qty = 0.0
        if not po_line.order_id.dest_address_id:
            supplierinfo_min_qty = self._get_supplier_min_qty(
                po_line.product_id, po_line.order_id.partner_id
            )

        rl_qty = 0.0
        # Recompute quantity by adding existing running procurements.
        for rl in po_line.purchase_request_lines:
            rl_qty += rl.product_uom_id._compute_quantity(rl.product_qty, purchase_uom)
        qty = max(rl_qty, supplierinfo_min_qty)
        return qty

    def _can_be_deleted(self):
        self.ensure_one()
        return self.request_state == "draft"

    def unlink(self):
        if self.mapped("purchase_lines"):
            raise UserError(
                _("You cannot delete a record that refers to purchase lines!")
            )
        for line in self:
            if not line._can_be_deleted():
                raise UserError(
                    _(
                        "You can only delete a purchase request line "
                        "if the purchase request is in draft state."
                    )
                )
        return super().unlink()

    def action_show_details(self):
        self.ensure_one()
        view = self.env.ref("purchase_request.view_purchase_request_line_details")
        return {
            "name": _("Detailed Line"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "purchase.request.line",
            "views": [(view.id, "form")],
            "view_id": view.id,
            "target": "new",
            "res_id": self.id,
            "context": dict(
                self.env.context,
            ),
        }

    # Champ dupliqué plus haut avec libellé anglais, on conserve la
    # première définition pour éviter les redéfinitions.
    # selected_for_po = fields.Boolean(string="Sélectionnée pour PO", default=False)
    # selectable_for_po = fields.Boolean(
    #     compute="_compute_selectable_for_po",
    #     string="Sélectionnable pour PO",
    #     store=False,
    # )

    @api.depends("request_id.state", "purchase_lines", "cancelled")
    def _compute_selectable_for_po(self):
        for rec in self:
            rec.selectable_for_po = (
                rec.request_id.state == "to_purchase"
                and not rec.cancelled
                and not rec.purchase_lines
            )

    @api.model
    def create(self, vals):
        """Empêche la création de lignes si la demande n'est pas en brouillon."""
        request = None
        request_id = vals.get("request_id") or self.env.context.get("default_request_id")
        if request_id:
            request = self.env["purchase.request"].browse(request_id)
        if request and request.state != "draft":
            raise UserError(
                _(
                    "You can only create a purchase request line if the purchase request is in draft state."
                )
            )
        return super().create(vals)

    def _get_profile_user_ids_by_type(self, profile_type):
        """Retourne tous les users rattachés à un profile_type donné.

        Combine :
        - les access_user_ids du profil
        - les access_line_ids actifs (user.profile.lines avec access_is_enabled True)
        """

        Profile = self.env["user.profiles"]
        # On sécurise un peu la casse : profile_type exact, lower et upper
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

    def _get_rcg_profile_user_ids(self):
        """Raccourci pour les utilisateurs du profile_type 'RCG'."""

        return self._get_profile_user_ids_by_type("RCG")

    def _get_ra_profile_user_ids(self):
        """Raccourci pour les utilisateurs du profile_type 'RA'."""

        return self._get_profile_user_ids_by_type("RA")

    def action_n22_line_approved(self, force=False):
            for req in self:
                do_super_approve = True
                #req.generate_approval_route()

                if req.state in ("n1_approval") and req.approval_route_id:

                    req.generate_approval_route()

                    if req.next_approval_stage_id:


                        #req._action_send_to_first_sequence()

                        do_super_approve = False
                        req.action_n1_line_approved()

                       
                        #raise UserError(_('action_n2_line_approved sur purchase.request.line id=%s') % req.current_approval_stage_id.sequence)

                        #super(PurchaseRequest, req.request_id).action_n1_line_approved()
                        #req.next_approval_stage_id.sudo().state = 'pending'
                        #req._action_approve()
                        #req._action_send_to_line_first_sequence() 
                        req._action_send_to_rnd_liner_approve()
                       
                        #req._action_send_to_approve("approved")
                        #req.action_make_line_decision('approved')

                        req.write({'state': 'rnd_pending'})
                        #for line in req.line_ids:
                        #req.write({'state': 'n1_approval'})
                        #req.write({"state": "n1_approval"})
               
               
                elif req.current_approval_stage_id:

                    #if req.current_approval_stage_id.sequence == 1:
                    #raise UserError('dddqww')
                    if req.current_approval_stage_id.sequence == 1:
                        approval_stage = req.current_approval_stage_id

                        #req.current_approval_stage_id.sudo().state = 'approved'
                        approvers = approval_stage.user_ids
                        names = approvers.mapped('name')
                        if self.env.user not in approvers and not self.env.is_superuser():
                             raise exceptions.AccessError(_("Ce %s doit être approuvé par %s") % (self._description, ' ou '.join(names)))

                        req.current_approval_stage_id.sudo().state = 'approved'
                        user_ids = req.get_rc_user_ids_from_budget_center() or []
                        #raise UserError(user_ids)
                        req.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                        stages = req.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
                        target_1 = stages.filtered(lambda s: s.sequence == 2)[:1]
                        target_final_rcb = stages.filtered(lambda s: s.sequence == 5)[:1]
                        if len(user_ids) > 0:
                          target_1.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                          target_final_rcb.sudo().write({'user_ids': [(6, 0, list(user_ids))]})

                        req._action_send_to_approve()

                        #raise UserError('dddd')

                        #req.action_make_line_decision('approved')

                        #for line in req.lisdne_ids:
                        req.write({'state': 'rcb_pending'})
                    elif req.current_approval_stage_id.sequence == 2:
                        approval_stage = req.current_approval_stage_id
                        # if not record.current_approval_stage_id:
                        #                     raise UserError(_("Ce %s n'est pas en cours d'approbation !") % self._description)
                        
                        approvers = approval_stage.user_ids
                        names = approvers.mapped('name')
                        if self.env.user not in approvers and not self.env.is_superuser():
                             raise exceptions.AccessError(_("Ce %s doit être approuvé par %s") % (self._description, ' ou '.join(names)))

                        # Récupère les utilisateurs du profile_type "RCG" (users directs + lignes actives)
                        rcg_user_ids = req._get_rcg_profile_user_ids() or []
                        if rcg_user_ids:
                            approval_stage.sudo().write({
                                'user_ids': [(6, 0, rcg_user_ids)],
                            })

                        req.current_approval_stage_id.sudo().state = 'approved'
                        req._action_send_to_approve()

                        #raise UserError('ddd')
                        #for line in req.line_ids:
                        req.write({'state': 'rcg_pending'})

                        #req.write({"state": "rcg_pending"})
                        #req.action_make_line_decision('approved')

                    elif req.current_approval_stage_id.sequence == 3:
                        approval_stage = req.current_approval_stage_id

                        approvers = approval_stage.user_ids
                        names = approvers.mapped('name')
                        if self.env.user not in approvers and not self.env.is_superuser():
                             raise exceptions.AccessError(_("Ce %s doit être approuvé par %s") % (self._description, ' ou '.join(names)))

                        # Récupère les utilisateurs du profile_type "RA" pour cette séquence 3
                        ra_user_ids = req._get_ra_profile_user_ids() or []
                        if ra_user_ids:
                            approval_stage.sudo().write({
                                'user_ids': [(6, 0, ra_user_ids)],
                            })

                        req.current_approval_stage_id.sudo().state = 'approved'
                        req._action_send_to_approve()
                        #for line in req.line_ids:
                        req.write({'state': 'to_purchase'})
                        
                        #req.write({"state": "to_purchase"})
                        #req.action_make_line_decision('approved')

                    elif req.current_approval_stage_id.sequence == 4:
                   
                        approval_stage = req.current_approval_stage_id
                        approvers = approval_stage.user_ids
                        names = approvers.mapped('name')
                        if self.env.user not in approvers and not self.env.is_superuser():
                             raise exceptions.AccessError(_("Ce %s doit être approuvé par %s") % (self._description, ' ou '.join(names)))
                        user_ids = req.get_rc_user_ids_from_budget_center() or []
                        #raise UserError(user_ids)
                        #req.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                        stages = req.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
                        target_final_rcb = stages.filtered(lambda s: s.sequence == 5)[:1]
                        if user_ids:
                          target_final_rcb.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                        req.current_approval_stage_id.sudo().state = 'approved'
                        req._action_send_to_approve()
                        #for line in req.line_ids:
                        #    line.write({'state': 'to_purchase'})

                        req.write({"state": "rcb_final_approval"})
                        ##req.action_make_line_decision('approved')

                    else:
                        approval_stage = req.current_approval_stage_id

                        #req.action_make_line_decision('approved')
                        approvers = approval_stage.user_ids
                        names = approvers.mapped('name')
                        if self.env.user not in approvers and not self.env.is_superuser():
                             raise exceptions.AccessError(_("Ce %s doit être approuvé par %s") % (self._description, ' ou '.join(names)))

                        req.current_approval_stage_id.sudo().state = 'approved'
                        req._action_send_to_approve()
                        do_super_approve = req._is_fully_approved()
                        if do_super_approve:
                            #try:
                            #for line in req.line_ids:
                            #   line.write({'state': 'to_purchase'})
                            req.write({"state": "approved"})
                                
                            # except Exception:
                            #     req.write({"state": "to_purchase"})
          
                    #raise UserError('ddd')

            return {}
    def action_n1_line_approved(self,force=False):
        # user-visible button / flow hook: block if this PR is already a child
        # for rec in self:
            


        #     if rec.x_split_parent:
        #         raise exceptions.UserError(_("Cette demande a déjà un parent; le split est désactivé."))
        return self.action_run_line_split()
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

        Budget = self.env["budget.analytic"].sudo()

        for req in self:
            # if req.x_split_parent:
            #     raise exceptions.UserError(
            #         _("Le split est désactivé : cette demande est déjà un enfant (parent %s).")
            #         % (req.x_split_parent.display_name)
            #     )

            center_map = {}  # {center_id: [line, line, ...]}
            log_messages = []

            # ------------------------------------------------------------
            # 1️⃣ ASSIGN EACH LINE TO A UNIQUE CENTER
            # ------------------------------------------------------------
            #for line in req.line_ids:

            # Detect poste (template or variant)
            poste = None
            tmpl = req.product_id.product_tmpl_id
            if "post_id" in tmpl._fields:
                    poste = tmpl.post_id
            if not poste and "post_id" in req.product_id._fields:
                    poste = req.product_id.post_id
            if not poste:
                    req.state = "rcg_pending"
                    raise exceptions.UserError(_("Poste budgétaire introuvable (ligne %s)") % req.id)

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

                    req.state = "n1_approval"
                    raise exceptions.UserError(
                        _("Aucun centre trouvé pour le poste %s (ligne %s)")
                        % (poste.display_name, req.id)
                    )

            # ------------------------------------------------------------
            # 2️⃣ CENTER RESOLUTION (department > profile > attitré)
            # ------------------------------------------------------------
            center = None

            if len(all_centers) == 1:
                    #center = matched_centers[0]
                    center = all_centers[0]

            else:
                    department = req.request_id.department_id or None #line.department_id
                    dept_centers = self.env["account.analytic.account"]
                    if department:
                       current_dept = department
                       while current_dept and not dept_centers:
                        dept_budget = Budget.search([("department_id", "=", current_dept.id)], limit=1)

                        if dept_budget:
                         for bl in dept_budget.budget_line_ids:
                              dept_centers |= bl_center_map.get(
                                     bl.id, self.env["account.analytic.account"]
                                 )
                        current_dept = current_dept.parent_id
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
                                    % (poste.display_name, req.id)
                                )

            center_map.setdefault(center.id, []).append(req)

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
                        ln.write({"analytic_distribution": analytic_map,'state': "rnd_pending"})
                    

            # ------------------------------------------------------------
            # 6️⃣ FINALIZE
            # ------------------------------------------------------------
            #req.x_split_children = [(6, 0, [c.id for c in children.values()])]
            #req.state = "rnd_pending"


    def _action_send_to_line_approve(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)

            partner_ids_set = set()
            user_ids_set = set()
            #for line in record.line_ids:
            product = record.product_id
            categ = product.categ_id if product else False
            profile = getattr(categ, 'user_profile_id', False)
            if profile:
                    #raise UserError(_('Profile trouvé: %s') % profile.name)
                    for user in getattr(profile, 'access_user_ids', self.env['res.users']):
                        if user.partner_id:
                            user_ids_set.add(user.id)
                            partner_ids_set.add(user.partner_id.id)

            # Fallback: si aucun partenaire trouvé via rnd_profile, notifier les approbateurs de l'étape suivante
            if not partner_ids_set and record.next_approval_stage_id:
                partner_ids_set.update(record.next_approval_stage_id.user_ids.mapped('partner_id').ids)

            if partner_ids_set:
                record.message_post(body=message_body, partner_ids=list(partner_ids_set))

           
            else:
                # Pas de partenaires à notifier, au moins logguer l’évènement
                record.message_post(body=message_body)

                #user_ids=record.next_approval_stage_id.user_ids.mapped('id')
            record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})

            if record.next_approval_stage_id:

                record.next_approval_stage_id.sudo().state = 'pending'
                #record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})
                #raise AccessError(record.current_approval_stage_id.user_ids.ids)

