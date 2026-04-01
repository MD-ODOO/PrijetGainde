from odoo import models, fields, api, _, exceptions
from . import selection


class PurchaseRequest(models.Model):
        """Extension Gainde du modèle purchase.request.

        Cette classe reprend la logique d'approbation auparavant définie dans
        `xf_approval_route_purchase` afin de la centraliser dans le module
        personnalisé `purchase_gainde`.
        """
        _name = "purchase.request"
        _inherit = ["purchase.request", "approval.route.document"]

        approval_route_id = fields.Many2one(
            comodel_name="approval.route",
            readonly=True,
        )
        all_used_products = fields.Many2many(
            string="All Used Products",
            comodel_name="product.product",
            compute="_compute_all_used_products",
        )
        all_used_analytic_accounts = fields.Many2many(
            string="All Used Analytic Accounts",
            comodel_name="account.analytic.account",
            compute="_compute_all_used_analytic_accounts",
        )
        approval_stage_name = fields.Char(
            string="Approval Stage",
            compute="_compute_approval_stage_name",
            readonly=True,
        )

        # Indique si toutes les lignes ont exactement le même état
        all_lines_same_state = fields.Boolean(
            string="All Lines Same State",
            compute="_compute_all_lines_same_state",
        )

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
                                analytic_account_ids += [
                                    int(x) for x in aa_ids if x.isdigit()
                                ]
                            except Exception:
                                # skip malformed keys
                                continue
                req.all_used_analytic_accounts = list(set(analytic_account_ids))

        @api.depends("current_approval_stage_id")
        def _compute_approval_stage_name(self):
            for rec in self:
                rec.approval_stage_name = (
                    rec.current_approval_stage_id.name
                    if rec.current_approval_stage_id
                    else False
                )

        @api.depends("line_ids.state")
        def _compute_all_lines_same_state(self):
            for req in self:
                states = req.line_ids.mapped("state")
                req.all_lines_same_state = bool(states) and len(set(states)) == 1

        def _get_main_analytic_account(self):
            """Retourne l'analytic account principal de la demande.

            Supposé unique (toutes les lignes partagent le même centre budgétaire).
            """

            self.ensure_one()
            AA = self.env["account.analytic.account"]
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
            AA = self.env["account.analytic.account"]
            for ln in self.line_ids:
                dist = ln.analytic_distribution or {}
                if not dist:
                    continue
                key = next(iter(dist.keys()), None)  # ex: "center_id,poste_id"
                if not key:
                    continue
                try:
                    center_id = int(str(key).split(",")[0])
                except Exception:
                    continue
                center = AA.browse(center_id).with_context(active_test=False)
                if center.exists():
                    return center
            return AA.browse(False)

        def get_rc_user_ids_from_budget_center(self):
            """Récupère les users depuis le profil du centre budgétaire.

            Combine :
            - les utilisateurs des lignes de profil actives
              (user.profile.lines avec access_is_enabled = True,
              donc aujourd'hui dans [access_date_from ; access_date_to]),
            - et les access_user_ids du profil lui-même.

            On retourne l'union distincte de ces deux ensembles.
            """

            self.ensure_one()
            center = self._get_budgetary_center()

            user_ids = set()
            profile = getattr(center, "bc_user_profile", False) if center else False
            if profile:
                # 1) Lignes de profil actives (fenêtre de dates OK)
                enabled_lines = profile.access_line_ids.filtered(
                    lambda l: l.access_is_enabled
                )
                user_ids.update(enabled_lines.mapped("access_user_id.id"))

                # 2) Utilisateurs directement rattachés au profil
                user_ids.update(profile.access_user_ids.ids)

            return list(user_ids)

        def get_rc_partner_ids_from_budget_center(self):
            self.ensure_one()
            user_ids = self.get_rc_user_ids_from_budget_center()
            # On retourne les IDs utilisateurs (comme dans l'implémentation d'origine)
            return user_ids

        def _action_send_to_first_sequence(self):
            for record in self:
                # use sudo as purchase user cannot update purchase.order.approver
                message_body = _(
                    """
                Dear colleagues,
                You have been requested to approve the %s "%s"
                """
                ) % (self._description, record.display_name)
                partner = (
                    self.requested_by.employee_id.coach_id.user_id.partner_id
                    if self.requested_by
                    and self.requested_by.employee_id
                    and self.requested_by.employee_id.coach_id
                    and self.requested_by.employee_id.coach_id.user_id
                    and self.requested_by.employee_id.coach_id.user_id.partner_id
                    else False
                )

                if partner is not False:
                    record.message_post(body=message_body, partner_ids=[partner.id])
                    user_id = self.requested_by.employee_id.coach_id.user_id.id
                    if user_id:
                        record.current_approval_stage_id.sudo().write(
                            {"user_ids": [(6, 0, list(set([user_id])))]}
                        )

                else:
                    raise exceptions.UserError(_("Le demandeur n'a pas de superieur assigné."))
                record.next_approval_stage_id.sudo().state = "pending"

      
        def action_line_approved(self, force=False):
            """Approbation via les lignes : délègue aux actions de lignes."""

            for req in self:
                lines = req.line_ids
                if not lines:
                    raise exceptions.UserError(
                        _("La demande d'achat doit contenir au moins une ligne.")
                    )
                # Utilise la logique déjà définie sur les lignes
                lines.action_approve_lines()
            return {}

        def action_approve_all_lines(self):
            """Bouton en en-tête : approuver toutes les lignes.

            N'agit que si toutes les lignes ont le même état.
            """

            for req in self:
                lines = req.line_ids
                if not lines:
                    continue
                states = set(lines.mapped("state"))
                if len(states) != 1:
                    continue
                lines.action_approve_lines()
            return True

        def action_reject_all_lines(self):
            """Bouton en en-tête : rejeter toutes les lignes.

            N'agit que si toutes les lignes ont le même état.
            """

            for req in self:
                lines = req.line_ids
                if not lines:
                    continue
                states = set(lines.mapped("state"))
                if len(states) != 1:
                    continue
                lines.action_reject_lines()
            return True


        def _approval_allowed(self):
            return True

        def button_to_approve(self):
            """Override pour générer la route et passer en N+1 pending."""

            for req in self:
                if req.state == "draft" and req.approval_route_id:
                    req.generate_approval_route()

                    if req.next_approval_stage_id:
                        req._action_send_to_approve()
                        req.write({"state": "n1_approval"})

            return True

        def button_draft(self):
            """Réinitialise les étapes d'approbation et repasse en brouillon."""

            self._clear_approval_stages()
            return super(PurchaseRequest, self).button_draft()

        def _get_default_approval_route_for_company(self, company):
            """Retourne la route par défaut pour purchase.request pour cette société (si dispo)."""

            route = self.env.ref(
                "xf_approval_route_purchase.xf_route_purchase_request_default",
                raise_if_not_found=False,
            )
            if route and (not route.company_id or route.company_id.id == company.id):
                return route
            domain = [
                ("model", "=", "purchase.request"),
                ("company_id", "in", [company.id, False]),
            ]
            return self.env["approval.route"].search(domain, limit=1)

        def action_jump_to_stage_3(self, reset_decisions=True):
            """Force la route d’approbation sur l’étape avec sequence = 3.

            Règles :
            - étapes < 3  → approved
            - étape 3     → pending
            - étapes > 3  → to approve
            """

            from odoo.exceptions import UserError, AccessError

            for req in self:
                if not req.approval_route_stage_ids:
                    req.generate_approval_route()

                stages = req.approval_route_stage_ids.sorted(
                    key=lambda s: (s.sequence, s.id)
                )
                target = stages.filtered(lambda s: s.sequence == 3)[:1]
                target_final_rcb = stages.filtered(lambda s: s.sequence == 5)[:1]

                if not target:
                    raise UserError(_("Aucune étape d'approbation avec sequence = 3."))

                if not (self.env.user == self.env.user or self.env.is_superuser()):
                    raise AccessError(_("Accès refusé."))

                for stage in stages:
                    vals = {}

                    if stage.sequence < 3:
                        vals["state"] = "approved"

                    elif stage.sequence == 3:
                        vals["state"] = "pending"
                        if reset_decisions:
                            vals["decisions"] = {}

                    else:
                        vals["state"] = "to approve"
                        if reset_decisions:
                            vals["decisions"] = {}

                    stage.sudo().write(vals)

                req.invalidate_recordset(
                    [
                        "current_approval_stage_id",
                        "next_approval_stage_id",
                        "is_under_approval",
                        "is_approval_received",
                        "is_fully_approved",
                    ]
                )

                user_ids = req.get_rc_partner_ids_from_budget_center() or []

                if user_ids:
                    target.sudo().write({"user_ids": [(6, 0, list(set(user_ids)))]})
                    if target_final_rcb:
                        target_final_rcb.sudo().write(
                            {"user_ids": [(6, 0, list(set(user_ids)))]}
                        )

                if hasattr(req, "state"):
                    req.sudo().write({"state": "rcb_pending"})

                if req.x_split_parent:
                    req.x_split_parent.sudo().write({"state": "rcb_pending"})

                # Si des lignes sont déjà approuvées/rejetées, on doit garder une synthèse
                # (approved/rejected/partially_approved) au lieu d'un état workflow.
                recompute = getattr(req.sudo(), "_recompute_state_from_lines", None)
                if callable(recompute):
                    recompute()
                if req.x_split_parent:
                    parent_recompute = getattr(req.x_split_parent.sudo(), "_recompute_state_from_lines", None)
                    if callable(parent_recompute):
                        parent_recompute()

                req.message_post(
                    body=_(
                        "Le workflow d’approbation a été repositionné sur l’étape "
                        "<b>%s</b> (toutes les étapes précédentes approuvées)."
                    )
                    % target.name
                )

        @api.model_create_multi
        def create(self, vals_list):
            new_vals_list = []
            for vals in vals_list:
                v = dict(vals)
                if "approval_route_id" not in v:
                    company_id = v.get("company_id", self.env.company.id)
                    company = self.env["res.company"].browse(company_id)
                    use_route = True
                    if use_route:
                        route = self._get_default_approval_route_for_company(company)
                        if route:
                            v["approval_route_id"] = route.id
                new_vals_list.append(v)
            return super(PurchaseRequest, self).create(new_vals_list)

        def write(self, vals):
            if "company_id" in vals and "approval_route_id" not in vals:
                for rec in self:
                    company = self.env["res.company"].browse(vals.get("company_id"))
                    if getattr(company, "use_approval_route_purchase", False) and not rec.approval_route_id:
                        route = self._get_default_approval_route_for_company(company)
                        if route:
                            super(PurchaseRequest, rec).write({"approval_route_id": route.id})
            return super(PurchaseRequest, self).write(vals)

        def _action_approve(self):
            """Override pour détecter un stage spécial 'Approbation N+1'."""

            stage_n1 = self.env.ref(
                "xf_approval_route_purchase.xf_stage_n1_approval",
                raise_if_not_found=False,
            )
            res = None
            for rec in self:
                if (
                    rec.current_approval_stage_id
                    and stage_n1
                    and rec.current_approval_stage_id.id == stage_n1.id
                ):
                    res = rec.action_n1_approved()
                else:
                    try:
                        # Appel du comportement standard d'approbation sur purchase.request
                        res = super(PurchaseRequest, rec)._action_approve()
                    except Exception:
                        res = None
            return res

        @api.model
        def assign_default_route_to_existing(self):
            """Assigne une route d'approbation par défaut aux PR existantes."""

            PR = self.search([("approval_route_id", "=", False)])
            if not PR:
                return 0
            default_ref = self.env.ref(
                "xf_approval_route_purchase.xf_route_purchase_request_default",
                raise_if_not_found=False,
            )
            updated = 0
            for pr in PR:
                company = pr.company_id or self.env.company
                if getattr(company, "use_approval_route_purchase", False):
                    route = default_ref
                    if not route or (route.company_id and route.company_id.id != company.id):
                        route = self.env["approval.route"].search(
                            [
                                ("model", "=", "purchase.request"),
                                ("company_id", "in", [company.id, False]),
                            ],
                            limit=1,
                        )
                    if route:
                        pr.write({"approval_route_id": route.id})
                        updated += 1
            return updated

        @api.model
        def action_assign_default_route_ui(self):
            """Action UI: assigne les routes par défaut et notifie le nombre MAJ."""

            updated = self.assign_default_route_to_existing()
            message = _(
                "%s demandes d'achat ont été mises à jour avec la route d'approbation par défaut."
            ) % (updated)
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

class PurchaseRequestLine(models.Model):
        """Extension Gainde du modèle purchase.request.

        Cette classe reprend la logique d'approbation auparavant définie dans
        `xf_approval_route_purchase` afin de la centraliser dans le module
        personnalisé `purchase_gainde`.
        """
        _name = "purchase.request.line"
        _inherit = ["purchase.request.line", "approval.route.document"]

        approval_route_id = fields.Many2one(
            comodel_name="approval.route",
            readonly=True,
        )
        all_used_products = fields.Many2many(
            string="All Used Products",
            comodel_name="product.product",
            compute="_compute_all_used_products",
        )
        all_used_analytic_accounts = fields.Many2many(
            string="All Used Analytic Accounts",
            comodel_name="account.analytic.account",
            compute="_compute_all_used_analytic_accounts",
        )
        approval_stage_name = fields.Char(
            string="Approval Stage",
            compute="_compute_approval_stage_name",
            readonly=True,
        )
        
      
        @api.model_create_multi
        def create(self, vals_list):
            new_vals_list = []
            for vals in vals_list:
                v = dict(vals)
                if "approval_route_id" not in v:
                    company_id = v.get("company_id", self.env.company.id)
                    company = self.env["res.company"].browse(company_id)
                    use_route = True
                    if use_route:
                        route = self._get_default_approval_route_for_company(company)
                        if route:

                            v["approval_route_id"] = route.id
                new_vals_list.append(v)
            return super(PurchaseRequestLine, self).create(new_vals_list)

        def write(self, vals):
            state_changed = "state" in vals
            if "company_id" in vals and "approval_route_id" not in vals:
                for rec in self:
                    company = self.env["res.company"].browse(vals.get("company_id"))
                    if getattr(company, "use_approval_route_purchase", False) and not rec.approval_route_id:
                        route = self._get_default_approval_route_for_company(company)
                        if route:
                            super(PurchaseRequestLine, rec).write({"approval_route_id": route.id})
            res = super(PurchaseRequestLine, self).write(vals)

            # Toute décision de ligne (approved/rejected) doit se refléter sur la demande
            # via _recompute_state_from_lines, sinon l'état peut rester bloqué sur rcb_pending.
            if state_changed:
                requests = self.mapped("request_id").sudo()
                recompute = getattr(requests, "_recompute_state_from_lines", None)
                if callable(recompute):
                    recompute()
            return res

        def _action_approve(self):
            """Override pour détecter un stage spécial 'Approbation N+1'."""

            stage_n1 = self.env.ref(
                "xf_approval_route_purchase.xf_stage_rnd_line_approval",
                raise_if_not_found=False,
            )
            res = None
            for rec in self:
                if (
                    rec.current_approval_stage_id
                    and stage_n1
                    and rec.current_approval_stage_id.id == stage_n1.id
                ):
                    res = rec.action_n1_approved()
                else:
                    try:
                        res = super(PurchaseRequestLine, rec)._action_approve()
                    except Exception:
                        res = None
            return res

        @api.model
        def assign_default_route_to_existing(self):
            """Assigne une route d'approbation par défaut aux PR existantes."""

            PR = self.search([("approval_route_id", "=", False)])
            if not PR:
                return 0
            default_ref = self.env.ref(
                "xf_approval_route_purchase.xf_route_purchase_request_line_default",
                raise_if_not_found=False,
            )
            updated = 0
            for pr in PR:
                company = pr.company_id or self.env.company
                if getattr(company, "use_approval_route_purchase", False):
                    route = default_ref
                    if not route or (route.company_id and route.company_id.id != company.id):
                        route = self.env["approval.route"].search(
                            [
                                ("model", "=", "purchase.request.line"),
                                ("company_id", "in", [company.id, False]),
                            ],
                            limit=1,
                        )
                    if route:
                        pr.write({"approval_route_id": route.id})
                        updated += 1
            return updated

        @api.model
        def action_assign_default_route_ui(self):
            """Action UI: assigne les routes par défaut et notifie le nombre MAJ."""

            updated = self.assign_default_route_to_existing()
            message = _(
                "%s demandes d'achat ont été mises à jour avec la route d'approbation par défaut."
            ) % (updated)
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
        def _get_default_approval_route_for_company(self, company):
            """Retourne la route par défaut pour purchase.request pour cette société (si dispo)."""

            route = self.env.ref(
                "xf_approval_route_purchase.xf_route_purchase_request_line_default",
                raise_if_not_found=False,
            )
            if route and (not route.company_id or route.company_id.id == company.id):
                return route
            domain = [
                ("model", "=", "purchase.request.line"),
                ("company_id", "in", [company.id, False]),
            ]
            return self.env["approval.route"].search(domain, limit=1)

        def action_make_line_decision(self, decision):
          for record in self:
            approval_stage = record.current_approval_stage_id
            # if not record.current_approval_stage_id:
            #                     raise UserError(_("Ce %s n'est pas en cours d'approbation !") % self._description)

            approvers = approval_stage.user_ids
            names = approvers.mapped('name')
            if self.env.user not in approvers and not self.env.is_superuser():
                raise exceptions.AccessError(_("Ce %s doit être approuvé par %s") % (self._description, ' ou '.join(names)))

            decisions = approval_stage.decisions or {}
            decisions.update({str(self.env.user.id): decision})
            approval_stage.decisions = decisions

            record.message_post(body=_('%s %s by %s') % (self._description, decision, self.env.user.name))
 
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

                record.message_post(body=_('%s was fully approved') % self._description)
            elif approval_stage.state == selection.APPROVAL_STATE_APPROVED and record.next_approval_stage_id:

                if record.current_approval_stage_id.sequence == 1:

                    # RND Approval Stage
                    user_ids = record.get_rc_user_ids_from_budget_center() or []
                    record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                    stages = record.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
                    target_1 = stages.filtered(lambda s: s.sequence == 2)[:1]
                    target_final_rcb = stages.filtered(lambda s: s.sequence == 5)[:1]
                    if target_final_rcb:
                        target_1.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                        target_final_rcb.sudo().write({'user_ids': [(6, 0, list(user_ids))]})

                    record._action_send_to_rnd_liner_approve()
                elif record.current_approval_stage_id.sequence == 2:

                    # RND Approval Stage
                    user_ids = record.get_rc_user_ids_from_budget_center() or []
                    record.next_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids))]})
                   
                    record._action_send_to_line_approve()

                elif record.current_approval_stage_id.sequence == 3:
                    # RND Approval Stage

                    record._action_send_to_line_approve()
                    
                elif record.current_approval_stage_id.sequence == 4:
                    # RND Approval Stage
           
                    record._action_send_to_line_approve()
                elif record.current_approval_stage_id.sequence == 5:
                    # RND Approval Stage
                  
                    record._action_send_to_line_approve()


        def _action_send_to_line_approve(self):
            for record in self:
                # use sudo as purchase user cannot update purchase.order.approver
                message_body = _('''
                Dear colleagues,
                You have been requested to approve the %s "%s"
                ''') % (self._description, record.display_name)

                partners = record.next_approval_stage_id.user_ids.mapped('partner_id')
                record.message_post(body=message_body, partner_ids=partners.ids)
                record.next_approval_stage_id.sudo().state = 'pending'
        def _action_send_to_rnd_liner_approve(self):
          for record in self:
            # use sudo as purchase user cannot update purchase.order.approver
            message_body = _('''
            Dear colleagues,
            You have been requested to approve the %s "%s"
            ''') % (self._description, record.display_name)

            partner_ids_set = set()
            user_ids_set = set()
            product = record.product_id
            categ = product.categ_id if product else False

            profile = getattr(categ, 'user_profile_id', False)

            if profile:
                    for user in getattr(profile, 'access_user_ids', self.env['res.users']):
                        if user.partner_id:

                            user_ids_set.add(user.id)
                            partner_ids_set.add(user.partner_id.id)

            else:
                raise exceptions.UserError('Pas de profile RND configuré pour cette nature de produit')

            # Fallback: si aucun partenaire trouvé via rnd_profile, notifier les approbateurs de l'étape suivante
            # if not partner_ids_set and record.next_approval_stage_id:

            #     partner_ids_set.update(record.next_approval_stage_id.user_ids.mapped('partner_id').ids)

            if partner_ids_set:
                #raise UserError(partner_ids_set)
                record.message_post(body=message_body, partner_ids=list(partner_ids_set))
                #record.current_approval_stage_id.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})
                stages = record.approval_route_stage_ids.sorted(key=lambda s: (s.sequence, s.id))
                target_1 = stages.filtered(lambda s: s.sequence == 1)[:1]
                if target_1:
                          target_1.sudo().write({'user_ids': [(6, 0, list(user_ids_set))]})


            else:
                raise exceptions.UserError('Pas d\'approbateur RND trouvé pour cette ligne de demande')
                # Pas de partenaires à notifier, au moins logguer l’évènement
                record.message_post(body=message_body)
                #user_ids=record.next_approval_stage_id.user_ids.mapped('id')

            if record.next_approval_stage_id:

                record.next_approval_stage_id.sudo().state = 'pending'

        def _get_main_analytic_account(self):
            """Retourne l'analytic account principal de la demande.

            Supposé unique (toutes les lignes partagent le même centre budgétaire).
            """

            self.ensure_one()
            AA = self.env["account.analytic.account"]
            # 1) Utiliser le computed all_used_analytic_accounts si dispo
            if self.all_used_analytic_accounts:
                return AA.browse(self.all_used_analytic_accounts.ids[0])
            # 2) Fallback: extraire le 1er ID depuis analytic_distribution des lignes
            #for line in self.line_ids:
            dist = self.analytic_distribution or {}
            if dist:
                    # Les clés sont des chaînes "id" ou "id,id"
                    first_key = next(iter(dist.keys()))
                    try:
                        ids = [int(x) for x in first_key.split(",") if x.isdigit()]
                        if ids:
                            return AA.browse(ids[0])
                    except Exception:
                        pass
            return AA.browse(False)

        def _get_budgetary_center(self):
            """Retourne le center (account.analytic.account) depuis analytic_distribution des lignes."""

            self.ensure_one()
            AA = self.env["account.analytic.account"]
            #for ln in self.line_ids:
            dist = self.analytic_distribution or {}
            if not dist:
                    return AA.browse(False)
            key = next(iter(dist.keys()), None)  # ex: "center_id,poste_id"
            if not key:
                    return AA.browse(False)
            try:
                    center_id = int(str(key).split(",")[0])
            except Exception:
                    return AA.browse(False)
            center = AA.browse(center_id).with_context(active_test=False)
            if center.exists():
                    return center
            return AA.browse(False)

        def get_rc_user_ids_from_budget_center(self):
            """Récupère les users depuis le profil du centre budgétaire.

            Même logique que sur l'entête : union distincte entre les
            utilisateurs des lignes de profil actives (user.profile.lines
            avec access_is_enabled) et les access_user_ids du profil.
            """

            self.ensure_one()
            center = self._get_budgetary_center()

            user_ids = set()
            profile = getattr(center, "bc_user_profile", False) if center else False
            if profile:
                enabled_lines = profile.access_line_ids.filtered(
                    lambda l: l.access_is_enabled
                )
                user_ids.update(enabled_lines.mapped("access_user_id.id"))
                user_ids.update(profile.access_user_ids.ids)

            return list(user_ids)

        def get_rc_partner_ids_from_budget_center(self):
            self.ensure_one()
            user_ids = self.get_rc_user_ids_from_budget_center()
            # On retourne les IDs utilisateurs (comme dans l'implémentation d'origine)
            return user_ids
            
        def _action_send_to_line_first_sequence(self):
            for record in self:
                # use sudo as purchase user cannot update purchase.order.approver
                message_body = _(
                    """
                Dear colleagues,
                You have been requested to approve the %s "%s"
                """
                ) % (self._description, record.display_name)
                partner = (
                    self.requested_by.employee_id.coach_id.user_id.partner_id
                    if self.requested_by
                    and self.requested_by.employee_id
                    and self.requested_by.employee_id.coach_id
                    and self.requested_by.employee_id.coach_id.user_id
                    and self.requested_by.employee_id.coach_id.user_id.partner_id
                    else False
                )

                if partner is not False:
                    record.message_post(body=message_body, partner_ids=[partner.id])
                    user_id = self.requested_by.employee_id.coach_id.user_id.id
                    if user_id:
                        record.current_approval_stage_id.sudo().write(
                            {"user_ids": [(6, 0, list(set([user_id])))]}
                        )

                else:
                    raise exceptions.UserError(_("Le demandeur n'a pas de superieur assigné."))
                record.next_approval_stage_id.sudo().state = "pending"

