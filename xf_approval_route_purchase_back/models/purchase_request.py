from odoo import models, fields, api, _, exceptions
import logging
_logger = logging.getLogger(__name__)

class PurchaseRequest(models.Model):
    _name = 'purchase.request'
    _inherit = ['purchase.request', 'approval.route.document']

    # use_approval_route = fields.Selection(
    #     string="Use Approval Route",
    #     related="company_id.use_approval_route_request",
    # )
    approval_route_id = fields.Many2one(
        comodel_name="approval.route",
        readonly=True,
    )
    all_used_products = fields.Many2many(
        string='All Used Products',
        comodel_name='product.product',
        compute="_compute_all_used_products",
    )
    all_used_analytic_accounts = fields.Many2many(
        string='All Used Analytic Accounts',
        comodel_name='account.analytic.account',
        compute="_compute_all_used_analytic_accounts",
    )
    approval_stage_name = fields.Char(string="Approval Stage", compute="_compute_approval_stage_name", readonly=True)

    @api.depends("line_ids.product_id")
    def _compute_all_used_products(self):
        for req in self:
            req.all_used_products = req.line_ids.mapped("product_id")

    @api.depends("line_ids.analytic_distribution")
    def _compute_all_used_analytic_accounts(self):
        for req in self:
            analytic_account_ids = []
            for line in req.line_ids:
                if line.analytic_distribution:
                    for aa_key in line.analytic_distribution.keys():
                        try:
                            aa_ids = aa_key.split(",")
                            analytic_account_ids += [int(x) for x in aa_ids if x.isdigit()]
                        except Exception:
                            # skip malformed keys
                            continue
            req.all_used_analytic_accounts = list(set(analytic_account_ids))
    
    @api.depends("current_approval_stage_id")
    def _compute_approval_stage_name(self):
        for rec in self:
            rec.approval_stage_name = rec.current_approval_stage_id.name if rec.current_approval_stage_id else False
    def _get_main_analytic_account(self):
        """
        Retourne l'analytic account principal de la demande.
        Supposé unique (toutes les lignes partagent le même centre budgétaire).
        """
        self.ensure_one()
        AA = self.env['account.analytic.account']
        # 1) Utiliser le computed all_used_analytic_accounts si dispo
        if self.all_used_analytic_accounts:
            return AA.browse(self.all_used_analytic_accounts.ids[0])
        # 2) Fallback: extraire le 1er ID depuis analytic_distribution des lignes
        for line in self.line_ids:
            dist = line.analytic_distribution or {}
            if dist:
                # Les clés sont des chaînes "id" ou "id,id"
                first_key = next(iter(dist.keys()))
                try:
                    ids = [int(x) for x in first_key.split(",") if x.isdigit()]
                    if ids:
                        return AA.browse(ids[0])
                except Exception:
                    continue
        return AA.browse(False)

    def _get_budgetary_center(self):
        """Retourne le center (account.analytic.account) depuis analytic_distribution des lignes."""
        self.ensure_one()
        AA = self.env['account.analytic.account']
        for ln in self.line_ids:
            dist = ln.analytic_distribution or {}
            if not dist:
                continue
            key = next(iter(dist.keys()), None)  # ex: "center_id,poste_id"
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
        """
        Récupère les users depuis le profil du centre budgétaire.
        Essaie plusieurs noms de champs, puis fallback sur user_ids du centre.
        """
        self.ensure_one()
        center = self._get_budgetary_center()
        users=center.bc_user_profile.access_user_ids.ids
        return list(set(users))

        if not center:
            raise exceptions.UserError('auccun')

            _logger.debug("PR %s: aucun centre budgétaire trouvé.", self.id)
            return []

        # Chercher le profil sur le center avec différents noms possibles
        profile = False
        for fname in ('bc_user_profile'):
            if fname in center._fields:

                prof = getattr(center, fname)

                if prof:
                    profile = prof
                    break

        users = self.env['res.users']
        if profile:
            # Supporte users_ids ou user_ids sur le profil
            if 'users_ids' in profile._fields:
                users |= profile.users_ids
            if 'user_ids' in profile._fields:
                users |= profile.user_ids

        # Fallback: directement des users sur le center
        for fname in ('rc_user_ids', 'user_ids'):
            if fname in center._fields:
                users |= getattr(center, fname)

        user_ids = list(set(users.ids))
        if not user_ids:
            _logger.debug(
                "PR %s: profil non trouvé ou vide sur center %s (champs testés).",
                self.id, center.id
            )
        return user_ids

    def get_rc_partner_ids_from_budget_center(self):
        self.ensure_one()
        user_ids = self.get_rc_user_ids_from_budget_center()
        return user_ids #self.env['res.users'].browse(user_ids).mapped('partner_id').ids
    # def action_n2_child_approved(self, force=False):
    #     for req in self:
    #         # Secure execution: do not run on children
    #         if not req.x_split_parent:
    #             raise exceptions.UserError(_("Cette demande doit avoir un parent."))
    #         do_super_approve = True
    #         if req.state in ("rnd_pending") and req.approval_route_id:

    #             req.generate_approval_route()
    #             if req.next_approval_stage_id:
    #                 #raise exceptions.UserError(req.next_approval_stage_id.sequence)
    #                 req._action_send_to_approve()

    #                 do_super_approve = False
    #                 req.write({'state': 'rcb_pending'})
                    
    #                 #req.current_approval_stage_id
    #                 #super(PurchaseRequest, req).action_n1_approved()
    #                 #req._action_approve()


    #                 #req.write({"state": "rnd_pending"})
    #         elif req.current_approval_stage_id:

    #             #if req.current_approval_stage_id.sequence == 1:
    #             #    try: 
    #             #      super(PurchaseRequest, req).action_n1_approved()
    #             #    except Exception:
    #             #       raise exceptions.UserError(_("Erreur lors de l'approbation N+1."))
    #             req._action_approve()

    #             #req._action_approve()

    #             else:


    #              req._action_approve()
    #              #raise exceptions.UserError(req.current_approval_stage_id.sequence) 
    #              #if(req.current_approval_stage_id.sequence == 1):
    #              #req._action_send_to_approve()
    #              #super(PurchaseRequest, req).action_n1_approved(force)
    #              #req._action_approve()
    #              do_super_approve = req._is_fully_approved()
    #              if do_super_approve:
    #               try:
    #                 #a=2
    #                 # Fall back to original approval if parent implements it, else set approved.
    #                 req.write({"state": "to_purchase"})

    #                 #super(PurchaseRequest, req).action_n1_approved(force)
    #               except Exception:
    #                 req.write({"state": "to_approve"})
    #     return {}




    def _action_send_to_first_sequence(self):
        for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)
            partner = (
             self.requested_by.employee_id.coach_id.user_id.partner_id  
             if self.requested_by
             and self.requested_by.employee_id
             and self.requested_by.employee_id.coach_id
             and self.requested_by.employee_id.coach_id.user_id
             and self.requested_by.employee_id.coach_id.user_id.partner_id
             else False )

            # partners =self.requested_by.employee_id.coach_id.user_id.partner_id.id  #in record.current_approval_stage_id.user_ids.mapped('partner_id')
            if partner is not False:

                record.message_post(body=message_body, partner_ids=[partner.id])
                user_id= self.requested_by.employee_id.coach_id.user_id.id
                if user_id:  
                   #raise exceptions.UserError(_("Le demandeur a pour superieur : %s.") % user_id)  
                   record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(set([user_id])))]})

            else: 
                raise exceptions.UserError(_("Le demandeur n'a pas de superieur assigné."))
            record.next_approval_stage_id.sudo().state = 'pending'
            #raise exceptions.UserError(partners.user_id.id)     
           

    def action_n2_approved(self, force=False):
        for req in self:
            # Secure execution: do not run on children
            #if req.x_split_parent and  req.state == 'n1_approval':
            #    raise exceptions.UserError(_("Cette demande a déjà un parent ; le routage d'approbation est désactivé."))
            do_super_approve = True
            if req.state in ("draft") and req.approval_route_id:
                if len(req.line_ids)<=0: 
                    raise exceptions.UserError(_("La demande d'achat doit contenir au moins une ligne."))
                req.generate_approval_route()
                if req.next_approval_stage_id:
                    #req._action_send_to_approve()
                    req._action_send_to_first_sequence()
                    
                    do_super_approve = False
                    req.write({'state': 'n1_approval'})
                    
                    

                    #super(PurchaseRequest, req).action_n1_approved()
                    #req._action_approve()


                    #req.write({"state": "rnd_pending"})
            elif req.current_approval_stage_id:
                #raise exceptions.UserError(req.current_approval_stage_id.sequence)

                if req.current_approval_stage_id.sequence == 1:
                    #try: 
                    # raise exceptions.UserError(_("Erreur lors de l'approbation N+1."))

                    super(PurchaseRequest, req).action_n1_approved()
                    #except Exception:
                    #    raise exceptions.UserError(_("sds lors de l'approbation N+1."))
                    req.action_make_apply_rnd_decision('approved')


                    #req._action_approve()
                elif  req.current_approval_stage_id.sequence == 3:

                    # try: 
                    #   super(PurchaseRequest, req).action_n2_approved()
                    # except Exception:
                    #     raise exceptions.UserError(_("Erreur lors de l'approbation RCB."))
                    # #req.action_make_apply_rcb_decision('approved')

                    req.write({"state": "rcg_pending"})
                    req._action_approve()
                elif  req.current_approval_stage_id.sequence == 4:

                    # try: 
                    #   super(PurchaseRequest, req).action_n2_approved()
                    # except Exception:
                    #     raise exceptions.UserError(_("Erreur lors de l'approbation RCB."))
                    # #req.action_make_apply_rcb_decision('approved')

                    req.write({"state": "to_purchase"})
                    req._action_approve()
                elif  req.current_approval_stage_id.sequence == 5:

                    # try: 
                    #   super(PurchaseRequest, req).action_n2_approved()
                    # except Exception:
                    #     raise exceptions.UserError(_("Erreur lors de l'approbation RCB."))
                    # #req.action_make_apply_rcb_decision('approved')

                    req.write({"state": "to_purchase"})
                    req._action_approve()
                else:


                 req._action_approve()
                 #raise exceptions.UserError(req.current_approval_stage_id.sequence) 
                 #if(req.current_approval_stage_id.sequence == 1):
                 #req._action_send_to_approve()
                 #super(PurchaseRequest, req).action_n1_approved(force)
                 #req._action_approve()
                 do_super_approve = req._is_fully_approved()
                 if do_super_approve:
                  try:
                    #a=2
                    # Fall back to original approval if parent implements it, else set approved.
                    req.write({"state": "to_purchase"})

                    #super(PurchaseRequest, req).action_n1_approved(force)
                  except Exception:
                    req.write({"state": "to_approve"})
        return {}

    def _approval_allowed(self):
        return True
    
    def button_to_approve(self):
        """Override to assign automatic approvers and transition to N+1 pending"""
        for req in self:
            if req.state != 'draft':
                continue
            do_super_approve = True
            if req.state in ("draft") and req.approval_route_id:

                req.generate_approval_route()
                # req.message_post(
                #     body=f"Purchase request {req.name} has been submitted for your validation.",
                #     partner_ids=[req.assigned_to.partner_id.id],
                #     subtype_xmlid='mail.mt_comment'
                # )

                if req.next_approval_stage_id:
                    #do_super_approve = False
                    req._action_send_to_approve()
                    # raise exceptions.UserError(_("La demande d'achat a été envoyée pour approbation N+1."))


                    #super(PurchaseRequest, req).action_n1_approved()
                    #req._action_approve()


                    req.write({"state": "n1_approval"})
                    #req._action_send_to_approve()
                
            # Assign N+1 from portal employee's manager
            #if record.portal_employee_id and record.portal_employee_id.portal_manager_id:
            #    record.x_n1_user_id = record.portal_employee_id.portal_manager_id
            #    # Set assigned_to to N+1 manager
            #    record.assigned_to = record.x_n1_user_id
            #    # Notify N+1
            #    record._notify_n1_manager()
            
            # Ensure RCB manager is assigned
            #if not record.x_rcb_user_id:
            #    record._assign_rcb_manager()
            
            # Ensure RA manager is assigned
            #if not record.x_ra_user_id:
            #    record._assign_ra_manager()
            
            # Assign RCG from system parameter
            #rcg_user_id = self.env['ir.config_parameter'].sudo().get_param('purchase_request_gainde.rcg_user_id')
            #if rcg_user_id:
            ##    record.x_rcg_user_id = int(rcg_user_id)
            
            # Update state to N+1 pending (which is the existing 'to_approve' state)
            #return super(PurchaseRequest, req).button_to_approve()
        
        return True

    def button_draft(self):
        """Clear approval stages and reset PR to draft"""
        self._clear_approval_stages()
        return super(PurchaseRequest, self).button_draft()

    def _get_default_approval_route_for_company(self, company):
        """Return the default route for purchase.request for this company (if any)."""
        # try reference first
        route = self.env.ref("xf_approval_route_purchase.xf_route_purchase_request_default", raise_if_not_found=False)
        if route and (not route.company_id or route.company_id.id == company.id):
            return route
        # fallback: search route by model and company
        domain = [("model", "=", "purchase.request"), ("company_id", "in", [company.id, False])]
        return self.env["approval.route"].search(domain, limit=1)
    # def action_jump_to_stage_3(self, approve_previous=False, reset_decisions=True):
    #     """
    #     Force la route d’approbation sur l’étape avec sequence=3.
    #     - target.state -> 'pending'
    #     - autres -> 'to_approve' (ou 'approved' si approve_previous et sequence<3)
    #     - décisions du target réinitialisées si reset_decisions
    #     """
    #     for req in self:
    #         # Générer la route si absente
    #         if not req.approval_route_stage_ids:
    #             req.generate_approval_route()

    #         stages = req.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
    #         target = stages.filtered(lambda s: s.sequence == 3)[:1]
    #         if not target:
    #             _logger.warning("Aucune étape d'approbation avec sequence=3 pour request id=%s", req.id)
    #             continue

    #         for stage in stages:
    #             if stage.id == target.id:
    #                 vals = {'state': 'pending'}
    #                 if reset_decisions:
    #                     vals['decisions'] = {}
    #                 stage.sudo().write(vals)
    #             else:
    #                 if approve_previous and stage.sequence < 3:
    #                     stage.sudo().write({'state': 'approved'})
    #                 else:
    #                     stage.sudo().write({'state': 'to approve'})
    #         req.sudo().write({'state': 'rcb_pending'})
    #         user_ids = req.get_rc_partner_ids_from_budget_center()
    #         req.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids))]})


    #         if req.x_split_parent:
    #              req.x_split_parent.sudo().write({'state': 'rcb_pending'}) 
    #         #raise exceptions.UserError(user_ids)    
    #         #raise exceptions.UserError(req.state)
    #         req._action_approve()

    #         #req.message_post(body=_("Le flux a été forcé sur l’étape '%s' (seq=3).") % target.name)
    def action_jump_to_stage_3(self, reset_decisions=True):
       """
       Force la route d’approbation sur l’étape avec sequence = 3
       Règles :
       - étapes < 3  → approved
       - étape 3     → to_approve
       - étapes > 3  → to_approve
       """
       for req in self:
        # 1️⃣ Générer la route si absente
        if not req.approval_route_stage_ids:
            req.generate_approval_route()

        stages = req.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
        target = stages.filtered(lambda s: s.sequence == 3)[:1]
        target_final_rcb = stages.filtered(lambda s: s.sequence == 5)[:1]

        if not target:
            raise UserError(_("Aucune étape d'approbation avec sequence = 3."))

        # 2️⃣ Sécurité
        if not (self.env.user == self.env.user or self.env.is_superuser()):
            raise AccessError(_("Accès refusé."))

        # 3️⃣ Appliquer les états
        for stage in stages:
            vals = {}

            if stage.sequence < 3:
                vals['state'] ='approved'

            elif stage.sequence == 3:
                vals['state'] = 'pending'
                if reset_decisions:
                    vals['decisions'] = {}

            else:
                vals['state'] = 'to approve'
                if reset_decisions:
                    vals['decisions'] = {}

            stage.sudo().write(vals)

        # 4️⃣ Recalcul des champs computed
        req.invalidate_recordset([
            'current_approval_stage_id',
            'next_approval_stage_id',
            'is_under_approval',
            'is_approval_received',
            'is_fully_approved',
        ])

        # 5️⃣ Définir les approbateurs de l’étape 3
        user_ids = req.get_rc_partner_ids_from_budget_center() or []

        # # Option stricte : coach uniquement
        # coach = self.env.user.employee_id.coach_id.user_id
        # if coach and coach.id in user_ids:
        #     user_ids = [coach.id]

        if user_ids:
            target.sudo().write({
                'user_ids': [(6, 0, list(set(user_ids)))]
            })
            target_final_rcb.sudo().write({
                'user_ids': [(6, 0, list(set(user_ids)))]
            })

        # 6️⃣ État métier
        if hasattr(req, 'state'):
            req.sudo().write({'state': 'rcb_pending'})

        # 7️⃣ Parent split
        if req.x_split_parent:
            req.x_split_parent.sudo().write({'state': 'rcb_pending'})
        #req._action_approve()

        # 8️⃣ Log
        req.message_post(
            body=_(
                "Le workflow d’approbation a été repositionné sur l’étape "
                "<b>%s</b> (toutes les étapes précédentes approuvées)."
            ) % target.name
        )

    @api.model_create_multi
    def create(self, vals_list):
        # For each new record, if approval_route_id not provided and company uses approval route,
        # assign the default route (if found).
        new_vals_list = []
        for vals in vals_list:
            v = dict(vals)
            if "approval_route_id" not in v:
                company_id = v.get("company_id", self.env.company.id)
                company = self.env["res.company"].browse(company_id)
                # handle boolean/value variants for 'use_approval_route_purchase'
                use_route = True #getattr(company, "use_approval_route_purchase", False)
                if use_route:
                    route = self._get_default_approval_route_for_company(company)
                    if route:
                        v["approval_route_id"] = route.id
            new_vals_list.append(v)
        return super(PurchaseRequest, self).create(new_vals_list)

    def write(self, vals):
        # If company changes and if approval_route_id missing, assign default route
        if "company_id" in vals and "approval_route_id" not in vals:
            for rec in self:
                company = self.env["res.company"].browse(vals.get("company_id"))
                if getattr(company, "use_approval_route_purchase", False) and not rec.approval_route_id:
                    route = self._get_default_approval_route_for_company(company)
                    if route:
                        # apply route per-record by calling super on single record to avoid writing
                        # the same vals for all when different
                        super(PurchaseRequest, rec).write({"approval_route_id": route.id})
            # continue to write other values
        return super(PurchaseRequest, self).write(vals)

    def _action_approve(self):
        """Override to detect a special stage 'Approbation N+1' and run mapped function."""
        # Try to resolve the N+1 stage reference
        stage_n1 = self.env.ref("xf_approval_route_purchase.xf_stage_n1_approval", raise_if_not_found=False)
        res = None
        # When stage is set and equals stage_n1, execute the special approval action
        for rec in self:
            if rec.current_approval_stage_id and stage_n1 and rec.current_approval_stage_id.id == stage_n1.id:
                # call special action for N+1 stage before continuing
                res = rec.action_n1_approved()
                # Not returning here - continue loop to process others.
            else:
                # fallback to default approve behavior if parent mixin provides it
                try:
                    res = super(PurchaseRequest, rec)._action_approve()
                except Exception:
                    # ignore if super not present; allow approval route mixin to handle state
                    res = None
        return res

    @api.model
    def assign_default_route_to_existing(self):
        """
        API helper: assign default approval route to existing PRs missing it.
        Returns number of records updated.
        """
        PR = self.search([("approval_route_id", "=", False)])
        if not PR:
            return 0
        default_ref = self.env.ref("xf_approval_route_purchase.xf_route_purchase_request_default", raise_if_not_found=False)
        updated = 0
        for pr in PR:
            company = pr.company_id or self.env.company
            if getattr(company, "use_approval_route_purchase", False):
                route = default_ref
                if not route or (route.company_id and route.company_id.id != company.id):
                    route = self.env["approval.route"].search(
                        [("model", "=", "purchase.request"), ("company_id", "in", [company.id, False])], limit=1
                    )
                if route:
                    pr.write({"approval_route_id": route.id})
                    updated += 1
        return updated
        
    def action_n2_approved(self, force=False):
        for req in self:
            # Secure execution: do not run on children
            #if req.x_split_parent and  req.state == 'n1_approval':
            #    raise exceptions.UserError(_("Cette demande a déjà un parent ; le routage d'approbation est désactivé."))
            do_super_approve = True
            if req.state in ("draft") and req.approval_route_id:
                if len(req.line_ids)<=0: 
                    raise exceptions.UserError(_("La demande d'achat doit contenir au moins une ligne."))
                req.generate_approval_route()
                if req.next_approval_stage_id:
                    #req._action_send_to_approve()
                    req._action_send_to_first_sequence()
                    
                    do_super_approve = False
                    req.write({'state': 'n1_approval'})
                    

                    #super(PurchaseRequest, req).action_n1_approved()
                    #req._action_approve()


                    #req.write({"state": "rnd_pending"})
            elif req.current_approval_stage_id:
                #raise exceptions.UserError(req.current_approval_stage_id.sequence)

                if req.current_approval_stage_id.sequence == 1:
                    #try: 
                    # raise exceptions.UserError(_("Erreur lors de l'approbation N+1."))

                    super(PurchaseRequest, req).action_n1_approved()
                    #except Exception:
                    #    raise exceptions.UserError(_("sds lors de l'approbation N+1."))
                    req.action_make_apply_rnd_decision('approved')


                    #req._action_approve()
                elif  req.current_approval_stage_id.sequence == 3:

                    # try: 
                    #   super(PurchaseRequest, req).action_n2_approved()
                    # except Exception:
                    #     raise exceptions.UserError(_("Erreur lors de l'approbation RCB."))
                    # #req.action_make_apply_rcb_decision('approved')

                    req.write({"state": "rcg_pending"})
                    req._action_approve()
                elif  req.current_approval_stage_id.sequence == 4:

                    # try: 
                    #   super(PurchaseRequest, req).action_n2_approved()
                    # except Exception:
                    #     raise exceptions.UserError(_("Erreur lors de l'approbation RCB."))
                    # #req.action_make_apply_rcb_decision('approved')

                    req.write({"state": "to_purchase"})
                    req._action_approve()
                elif  req.current_approval_stage_id.sequence == 5:

                    # try: 
                    #   super(PurchaseRequest, req).action_n2_approved()
                    # except Exception:
                    #     raise exceptions.UserError(_("Erreur lors de l'approbation RCB."))
                    # #req.action_make_apply_rcb_decision('approved')

                    req.write({"state": "rcb_approval"})
                    req._action_approve()
                else:


                 req._action_approve()
                 #raise exceptions.UserError(req.current_approval_stage_id.sequence) 
                 #if(req.current_approval_stage_id.sequence == 1):
                 #req._action_send_to_approve()
                 #super(PurchaseRequest, req).action_n1_approved(force)
                 #req._action_approve()
                 do_super_approve = req._is_fully_approved()
                 if do_super_approve:
                  try:
                    #a=2
                    # Fall back to original approval if parent implements it, else set approved.
                    req.write({"state": "approved"})

                    #super(PurchaseRequest, req).action_n1_approved(force)
                  except Exception:
                    req.write({"state": "rcb_approval"})
        return {}

    @api.model
    def action_assign_default_route_ui(self):
        """
        API helper: run assign_default_route_to_existing and return an action
        that shows a display_notification with the number of updated records.
        Accessible depuis serveur action / bouton.
        """
        updated = self.assign_default_route_to_existing()
        message = _("%s demandes d'achat ont été mises à jour avec la route d'approbation par défaut.") % (updated)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Migration"),
                "message": message,
                "sticky": False,
                "type": "success" if updated else "warning",
            },
        }

    # def action_jump_to_stage_3(self, approve_previous=False, reset_decisions=True):
    #     """
    #     Force la demande à passer à l'étape d'approbation de séquence 3.
    #     - L'étape seq=3 devient 'pending' (courante).
    #     - Les autres étapes redeviennent 'to_approve' (sauf option approve_previous).
    #     - Optionnel: approuver les étapes < 3 et réinitialiser les décisions.

    #     :param approve_previous: si True, les étapes avec sequence < 3 passent en 'approved'.
    #     :param reset_decisions: si True, les décisions du stage cible sont réinitialisées.
    #     """
    #     for req in self:
    #         # Générer la route si absente
    #         if not req.approval_route_stage_ids:
    #             req.generate_approval_route()

    #         stages = req.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
    #         target = stages.filtered(lambda s: s.sequence == 3)[:1]
    #         if not target:
    #             raise exceptions.UserError(_("Aucune étape d'approbation avec la séquence 3."))

    #         # Mise à jour des états des étapes
    #         for stage in stages:
    #             if stage.id == target.id:
    #                 vals = {'state': 'pending'}
    #                 if reset_decisions:
    #                     vals['decisions'] = {}
    #                 stage.write(vals)
    #             else:
    #                 if approve_previous and stage.sequence < 3:
    #                     stage.write({'state': 'approved'})
    #                 else:
    #                     stage.write({'state': 'to approve'})
    #         req._action_approve()
            # Laisser les compute mettre à jour current_approval_stage_id/next_approval_stage_id
            #req.message_post(body=_("Le flux d'approbation a été forcé sur l'étape '%s' (séquence 3).") % target.name)