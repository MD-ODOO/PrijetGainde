from odoo import models, api, _, exceptions, fields
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError


class PurchaseGaindePurchaseOrder(models.Model):
    _inherit = "purchase.order"

    state = fields.Selection(
        selection_add=[
            ("rejected", "Rejeté"),
        ],
        ondelete={"rejected": "set default"},
    )

    # Département demandeur de l'achat
    department_id = fields.Many2one(
        comodel_name="hr.department",
        string="Département",
        required=False,
        help="Département demandeur de la commande d'achat.",
    )
    description = fields.Text()


    # Mode de paiement souhaité pour la commande
    payment_method_id = fields.Many2one(
        comodel_name="account.payment.method.line",
        string="Mode de paiement",
        help="Méthode de paiement utilisée pour régler cette commande.",
    )

    purchase_request_count = fields.Integer(
        string="Demandes d'achat",
        compute="_compute_purchase_request_count",
    )

    # Champ attendu par certaines vues de l'approbation d'achat
    alternative_count = fields.Integer(
        string="Alternatives",
        compute="_compute_alternative_count",
    )

    # Indicateur calculé : la commande est-elle bloquante selon les règles montant/offres ?
    gainde_amount_blocked = fields.Boolean(
        string="Seuil montant HT bloquant",
        compute="_compute_gainde_amount_blocked",
        store=False,
    )

    # Champ attendu par certaines vues (commande alternative)
    is_alternative_order = fields.Boolean(
        string="Commande alternative",
        default=False,
    )

    alternative_sequence = fields.Integer(
        string="Séquence alternative",
        default=0,
    )

    original_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Commande d'origine",
    )

    alternative_order_ids = fields.One2many(
        comodel_name="purchase.order",
        inverse_name="original_order_id",
        string="Commandes alternatives",
    )
    

    # Permet de dépasser explicitement le budget (override de is_above_budget)
    is_out_of_budget_limit = fields.Boolean(
        string="Est un achat hors budget",
        help=(
            "Si coché, permet de valider la commande même si elle "
            "dépasse le budget (is_above_budget)."
        ),
    )

    # Indique si la commande est considérée comme urgente
    is_urgent_purchase = fields.Boolean(
        string="Est un achat urgent/Spécifique",
        help="Si coché, certaines règles de seuil montant/offres ne bloquent pas.",
    )

    # Vrai si l'utilisateur courant possède le profil DA
    is_current_user_da = fields.Boolean(
        string="Utilisateur DA",
        compute="_compute_is_current_user_da",
        store=False,
    )

    def _compute_is_current_user_da(self):
        current_user = self.env.user
        is_da = bool(getattr(current_user, "has_profile_da", False))
        for order in self:
            order.is_current_user_da = is_da

    # TDR lié à la commande (fiche de termes de référence)
    tdr_linked_id = fields.Many2one(
        comodel_name="purchase.tdr",
        string="TDR lié",
        help="Terme de référence associé à cette commande d'achat.",
    )

    # ------------------------------------------------------------
    # ROUTE D'APPROBATION GAINDÉE (RA / RCB dynamiques)
    # ------------------------------------------------------------

    def _compute_purchase_request_count(self):
        for order in self:
            requests = order.order_line.mapped("purchase_request_lines.request_id")
            order.purchase_request_count = len(requests)

    def _compute_alternative_count(self):
        for order in self:
            order.alternative_count = len(order.alternative_order_ids)

    def action_view_purchase_requests(self):
        self.ensure_one()
        requests = self.order_line.mapped("purchase_request_lines.request_id")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase_request.purchase_request_form_action"
        )
        action["domain"] = [("id", "in", requests.ids)]
        return action

    def action_view_alternatives(self):
        """Action de secours pour éviter l'erreur de validation de vue.

        Certains environnements héritent d'un bouton 'action_view_alternatives'
        dans la vue d'achat. Si aucune action métier n'est définie, on retourne
        un résultat neutre.
        """

        return True

    @api.model
    def action_open_rfq_with_my_approvals(self):
        action = self.env["ir.actions.actions"]._for_xml_id("purchase.purchase_rfq")
        has_my_approvals = self.search_count([
            ("current_approval_stage_id.user_ids", "in", self.env.user.id)
        ]) > 0
        if has_my_approvals:
            ctx = action.get("context", {})
            if isinstance(ctx, str):
                try:
                    ctx = safe_eval(ctx)
                except Exception:
                    ctx = {}
            if not isinstance(ctx, dict):
                try:
                    ctx = dict(ctx)
                except Exception:
                    ctx = {}
            ctx = dict(ctx or {})
            ctx["search_default_my_approvals"] = 1
            action["context"] = ctx
        return action

    def _get_budgetary_centers(self):
        """Retourne les centres budgétaires trouvés sur les lignes de commande.

        On lit les clés de analytic_distribution ("center_id,poste_id")
        et on en déduit les account.analytic.account concernés.
        """

        self.ensure_one()
        AnalyticAccount = self.env["account.analytic.account"]
        centers = AnalyticAccount.browse()

        for line in self.order_line:
            dist = getattr(line, "analytic_distribution", False) or {}
            for key in dist.keys():
                try:
                    center_id = int(str(key).split(",")[0])
                except Exception:
                    continue
                if center_id:
                    centers |= AnalyticAccount.browse(center_id)

        return centers

    def get_rc_user_ids_from_budget_center(self):
        """Récupère les users RCB depuis les centres budgétaires de la commande.

        Même philosophie que sur purchase.request : pour chaque centre, on
        prend le profil ``bc_user_profile`` et on combine :
        - les utilisateurs des lignes de profil actives (user.profile.lines
          avec access_is_enabled = True),
        - et les access_user_ids du profil lui-même.

        On retourne l'union distincte de ces ensembles pour tous les centres
        trouvés sur les lignes de la commande.
        """

        self.ensure_one()

        user_ids = set()
        centers = self._get_budgetary_centers()
        for center in centers:
            profile = getattr(center, "bc_user_profile", False)
            if not profile:
                continue

            # Lignes de profil actives
            enabled_lines = profile.access_line_ids.filtered(
                lambda l: getattr(l, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))

            # Utilisateurs directement rattachés au profil
            user_ids.update(profile.access_user_ids.ids)

        return list(user_ids)

    def _get_ra_user_ids_from_profiles(self):
        """Retourne les utilisateurs RA Achats (profile_type = 'ra').

        On prend les utilisateurs directement rattachés au profil et ceux
        provenant des lignes de profil actives (access_is_enabled = True).
        """

        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "ra")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def _get_da_user_ids_from_profiles(self):
        """Retourne les utilisateurs DA (profile_type = 'da').

        Même logique que RA : on prend les utilisateurs directement rattachés
        au profil et ceux provenant des lignes de profil actives
        (access_is_enabled = True).
        """

        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "da")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        return list(user_ids)

    def _get_rcg_user_ids_from_profiles(self, required=False):
        """Retourne les utilisateurs RCG (profile_type = 'rcg').

        Si ``required`` est True, on bloque explicitement si aucun utilisateur
        n'est configuré (profil sensible).
        """

        Profile = self.env["user.profiles"]
        profiles = Profile.search([("profile_type", "=", "rcg")])

        user_ids = set()
        for profile in profiles:
            enabled_lines = profile.access_line_ids.filtered(
                lambda line: getattr(line, "access_is_enabled", False)
            )
            user_ids.update(enabled_lines.mapped("access_user_id.id"))
            user_ids.update(profile.access_user_ids.ids)
        user_ids = list(user_ids)

        if required and not user_ids:
            raise UserError(
                _(
                    "Aucun utilisateur RCG n'est configuré.\n\n"
                    "Veuillez créer/activer au moins un profil de type 'rcg' "
                    "(user.profiles) avec des utilisateurs, puis réessayer."
                )
            )

        return user_ids

    def _has_linked_purchase_request(self):
        self.ensure_one()
        return bool(self.order_line.mapped("purchase_request_lines.request_id"))

    def _get_default_approval_route_for_order(self, company):
        """Choisit la route selon le lien à une demande d'achat.

        - Si la commande N'est PAS liée à une purchase.request : route RCG→RCB→DA.
        - Sinon (liée à une PR) : route par défaut (RCB→DA).
        """

        self.ensure_one()

        if not self._has_linked_purchase_request():
            route = self.env.ref(
                "purchase_gainde.xf_route_purchase_order_with_pr",
                raise_if_not_found=False,
            )
            if route and (not route.company_id or route.company_id.id == company.id):
                return route

        return self._get_default_approval_route_for_company(company)

    @api.model
    def _gainde_disable_purchase_reports(self):
        """Désactive les rapports d'impression des commandes d'achat."""
        Report = self.env["ir.actions.report"].sudo()
        reports = Report.search([
            "|",
            ("report_name", "in", ["purchase.report_purchaseorder", "purchase.report_purchasequotation"]),
            ("report_file", "in", ["purchase.report_purchaseorder", "purchase.report_purchasequotation"]),
        ])
        if reports:
            vals = {}
            if "active" in Report._fields:
                vals["active"] = False
            # En Odoo 18, retirer le binding masque l'action d'impression
            if "binding_model_id" in Report._fields:
                vals["binding_model_id"] = False
            if vals:
                reports.write(vals)

    def button_approve(self, force=False):
        """Surcharge du bouton d'approbation pour RCB/RA dynamiques.

        - Comporte la logique standard d'xf_approval_route_purchase.
                - Pour l'étape sequence == 1 (RCB), on injecte les approbateurs
                    dynamiquement depuis les centres budgétaires.
                - Quand l'étape sequence == 1 est approuvée, on prépare l'étape
                    sequence == 2 (RA Achats) en injectant les utilisateurs issus
                    des profils de type "ra".
        """

        for order in self:
            # Check partner approval
            not_approved_partner = order.partner_id.approval_state != "approved"
            if not_approved_partner:
                raise UserError(
                    _("Impossible d'imprimer : le fournisseur doit être approuvé.")
                )

            # Check product approval on order lines
            not_approved_products = order.order_line.filtered(
                lambda l: l.product_id and l.product_id.approval_state != "approved"
            )
            if not_approved_products:
                raise UserError(
                    _("Impossible d'imprimer : tous les produits doivent être approuvés.")
                )

            do_super_approve = True

            # Assurer la bonne route (avec PR vs sans PR) avant démarrage
            if order.state in ("draft", "sent") and not order.current_approval_stage_id:
                company = order.company_id or self.env.company
                desired_route = order._get_default_approval_route_for_order(company)
                if desired_route and order.approval_route_id != desired_route:
                    order.sudo().write({"approval_route_id": desired_route.id})

            # Démarrage du circuit d'approbation
            if order.state in ("draft", "sent") and order.approval_route_id:
                # Generate approval route and send PO to approve
                order.generate_approval_route()
                if order.next_approval_stage_id:
                    stage = order.next_approval_stage_id
                    

                    # Étape 1 :
                    # - commande directe (sans PR, route with_pr) => RCG via profils
                    # - commande issue d'une PR (route default) => RCB via centres budgétaires
                    if stage.sequence == 1:
                        is_pr_route = order.approval_route_id == order.env.ref(
                            "purchase_gainde.xf_route_purchase_order_with_pr",
                            raise_if_not_found=False,
                        )

                        if is_pr_route:
                            rcg_user_ids = order._get_rcg_user_ids_from_profiles(required=True) or []
                            if rcg_user_ids:
                                stage.sudo().write({
                                    "user_ids": [(6, 0, list(rcg_user_ids))],
                                })
                                if order.current_approval_stage_id:
                                    order.current_approval_stage_id.sudo().write(
                                        {"user_ids": [(6, 0, list(rcg_user_ids))]}
                                    )
                        else:
                            rc_user_ids = order.get_rc_user_ids_from_budget_center() or []
                            if rc_user_ids:
                                stage.sudo().write({
                                    "user_ids": [(6, 0, list(rc_user_ids))],
                                })
                                if order.current_approval_stage_id:
                                    order.current_approval_stage_id.sudo().write(
                                        {"user_ids": [(6, 0, list(rc_user_ids))]}
                                    )


                    do_super_approve = False
                    # If approval route is generated and there is next approver mark the order "to approve"
                    order.write({"state": "to approve"})
                    # And send request to approve
                    order._action_send_to_approve()

            # Approvals en cours
            elif order.current_approval_stage_id:
                stage = order.current_approval_stage_id

                pr_route = order.env.ref(
                    "purchase_gainde.xf_route_purchase_order_with_pr",
                    raise_if_not_found=False,
                )
                is_pr_route = bool(pr_route and order.approval_route_id == pr_route)

                if is_pr_route:
                    # Route directe (sans PR, route with_pr) :
                    # seq1 (RCG) => recalcul analytique + préparation seq2 (RCB)
                    if stage.sequence == 1:
                        order._gainde_compute_analytic_distribution()

                        rc_user_ids = order.get_rc_user_ids_from_budget_center() or []
                        if rc_user_ids and order.next_approval_stage_id:
                            order.next_approval_stage_id.sudo().write({
                                "user_ids": [(6, 0, list(rc_user_ids))],
                            })

                    # seq2 (RCB) => préparation seq3 (DA)
                    if stage.sequence == 2:
                        da_user_ids = order._get_da_user_ids_from_profiles() or []
                        if da_user_ids and order.next_approval_stage_id:
                            order.next_approval_stage_id.sudo().write({
                                "user_ids": [(6, 0, list(da_user_ids))],
                            })
                else:
                    # Route issue d'une PR (route default) : seq1 (RCB) => préparation seq2 (DA)
                    if stage.sequence == 1:
                        da_user_ids = order._get_da_user_ids_from_profiles() or []
                        if da_user_ids and order.next_approval_stage_id:
                            order.next_approval_stage_id.sudo().write({
                                "user_ids": [(6, 0, list(da_user_ids))],
                            })

                order._action_approve()
                do_super_approve = order._is_fully_approved()

            if do_super_approve:
                super(PurchaseGaindePurchaseOrder, order).button_approve(force)

        return {}

    def button_reject(self):
        """Rejeter la commande d'achat en cours d'approbation."""
        for order in self:
            if order.current_approval_stage_id:
                order._action_reject()
            order.write({"state": "rejected"})
            order.message_post(body=_("Commande rejetée par %s", self.env.user.name))
        return {}

    def button_retourner(self):
        """Retourner la commande d'achat en brouillon et notifier les utilisateurs RA."""
        for order in self:
            order._clear_approval_stages()
            order.write({"state": "draft"})
            order.message_post(body=_("Commande retournée en brouillon par %s", self.env.user.name))

            # Envoyer un mail aux utilisateurs RA via le template
            ra_user_ids = order._get_ra_user_ids_from_profiles()
            if ra_user_ids:
                ra_users = self.env["res.users"].browse(ra_user_ids)
                ra_partners = ra_users.mapped("partner_id").filtered("email")
                template = self.env.ref(
                    "purchase_gainde.email_template_purchase_order_retourner",
                    raise_if_not_found=False,
                )
                if template and ra_partners:
                    template.send_mail(
                        order.id,
                        force_send=True,
                        email_values={
                            "recipient_ids": [(4, pid) for pid in ra_partners.ids],
                        },
                    )
        return {}

    def _get_default_approval_route_for_company(self, company):
        """Retourne la route d'approbation par défaut pour purchase.order.

        On privilégie la route définie dans purchase_gainde, puis on
        cherche toute route sur le modèle purchase.order pour la société.
        """

        route = self.env.ref(
            "purchase_gainde.xf_route_purchase_order_default",
            raise_if_not_found=False,
        )
        if route and (not route.company_id or route.company_id.id == company.id):
            return route

        domain = [
            ("model", "=", "purchase.order"),
            ("company_id", "in", [company.id, False]),
        ]
        return self.env["approval.route"].search(domain, limit=1)

    @api.constrains("original_order_id", "partner_id")
    def _check_alternative_supplier(self):
        """Empêche de créer une alternative avec le même fournisseur que la commande d'origine."""
        for order in self:
            if order.original_order_id and order.partner_id:
                if order.partner_id.id == order.original_order_id.partner_id.id:
                    raise UserError(
                        _("Impossible de créer une commande alternative avec le même fournisseur.\n"
                          "Veuillez sélectionner un fournisseur différent de la commande d'origine.")
                    )

    @api.model_create_multi
    def create(self, vals_list):
        """Renseigne la route d'approbation et le département par défaut.

        - Si ``approval_route_id`` n'est pas fourni, on affecte la route
          par défaut pour la société.
        - Si ``department_id`` n'est pas fourni, on le récupère depuis la
          première purchase.request liée aux lignes de commande créées.
        """

        new_vals_list = []
        for vals in vals_list:
            v = dict(vals)
            # Vérifier que les alternatives n'ont pas le même fournisseur que la commande d'origine
            if v.get("original_order_id") and v.get("partner_id"):
                original = self.env["purchase.order"].browse(v.get("original_order_id"))
                if original.partner_id.id == v.get("partner_id"):
                    raise UserError(
                        _("Impossible de créer une commande alternative avec le même fournisseur.\n"
                          "Veuillez sélectionner un fournisseur différent de la commande d'origine.")
                    )
            
            # Si aucune route n'est encore définie (clé absente ou valeur falsy),
            # on affecte la route par défaut pour la société.
            if not v.get("approval_route_id"):
                company_id = v.get("company_id", self.env.company.id)
                company = self.env["res.company"].browse(company_id)
                # Même logique que sur purchase.request : on active
                # toujours la route si disponible.
                use_route = True
                if use_route:
                    route = self._get_default_approval_route_for_company(company)
                    if route:
                        v["approval_route_id"] = route.id
            new_vals_list.append(v)

        orders = super(PurchaseGaindePurchaseOrder, self).create(new_vals_list)

        for order in orders:
            # Définir automatiquement la bonne route si absente
            if not order.approval_route_id:
                company = order.company_id or self.env.company
                route = order._get_default_approval_route_for_order(company)
                if route:
                    order.approval_route_id = route.id

            if not order.department_id:
                pr = (
                    order.order_line
                    .mapped("purchase_request_lines.request_id")
                    .filtered(lambda r: r.department_id)[:1]
                )
                if pr:
                    order.department_id = pr.department_id.id

        return orders

    # ------------------------------------------------------------------
    # ANALYTIQUE PAR LIGNE
    # ------------------------------------------------------------------
    def _gainde_compute_analytic_distribution_for_line(self, line):
        """Calcule et applique l'analytic_distribution pour UNE ligne de PO.

        La logique de calcul reprend celle de
        ``purchase.request.line.action_run_line_split`` :
        - Détection du poste budgétaire (product.template.post_id ou product.post_id)
        - Recherche des centres budgétaires via budget.analytic
        - Résolution du centre (département > profil > attitré)
        - Application d'une distribution 100% sur (center_id, poste_id)
        """

        Budget = self.env["budget.analytic"]
        AnalyticAccount = self.env["account.analytic.account"]

        product = line.product_id
        if not product:
            return

        budgets = Budget.search([])

        # 1) Détection du poste budgétaire
        poste = None
        tmpl = product.product_tmpl_id
        if "post_id" in tmpl._fields:
            poste = tmpl.post_id
        if not poste and "post_id" in product._fields:
            poste = product.post_id

        if not poste:
            # Même philosophie que sur purchase.request.line : on bloque
            raise exceptions.UserError(
                _("Poste budgétaire introuvable pour la ligne de commande %s")
                % (line.display_name,)
            )

        poste_id = poste.id

        # 1bis) Construire la table budget_line -> centres pour ce poste
        bl_center_map = {}
        all_centers = AnalyticAccount

        for budget in budgets:
            for bl in budget.budget_line_ids:
                poste_matched = False
                centers_for_bl = AnalyticAccount

                for fname, fdef in bl._fields.items():
                    if getattr(fdef, "comodel_name", None) != "account.analytic.account":
                        continue
                    if fdef.type not in ("many2one", "many2many"):
                        continue

                    recs = getattr(bl, fname) or AnalyticAccount

                    if poste_id in recs.ids and any(a.is_budgetary_poste for a in recs):
                        poste_matched = True

                    centers_for_bl |= recs.filtered(lambda a: a.is_budgetary_center)

                if poste_matched and centers_for_bl:
                    bl_center_map[bl.id] = centers_for_bl
                    all_centers |= centers_for_bl

        if not all_centers:
            raise exceptions.UserError(
                _("Aucun centre trouvé pour le poste %s (ligne de commande %s)")
                % (poste.display_name, line.display_name)
            )

        # 2) Résolution du centre (department > profile > attitré)
        center = None

        if len(all_centers) == 1:
            center = all_centers[0]
        else:
            # Département : pris depuis la première ligne de demande liée, si existante
            department = False
            pr_line = line.purchase_request_lines[:1]
            if pr_line and pr_line.request_id:
                department = pr_line.request_id.department_id

            dept_centers = AnalyticAccount
            if department:
                current_dept = department
                while current_dept and not dept_centers:
                    dept_budget = Budget.search([("department_id", "=", current_dept.id)], limit=1)
                    if dept_budget:
                        for bl in dept_budget.budget_line_ids:
                            dept_centers |= bl_center_map.get(bl.id, AnalyticAccount)
                    current_dept = current_dept.parent_id

            scope = dept_centers or all_centers

            if len(scope) == 1:
                center = scope[0]
            else:
                profile = getattr(poste, "bp_user_profile", False)
                profile_centers = (
                    scope.filtered(lambda c: c.bc_user_profile == profile)
                    if profile
                    else scope
                )

                if len(profile_centers) == 1:
                    center = profile_centers[0]
                else:
                    attitre_centers = profile_centers.filtered(
                        lambda c: c.bc_user_profile == profile
                    )
                    if len(attitre_centers) == 1:
                        center = attitre_centers[0]
                    else:
                        if len(attitre_centers) == 0 :
                            raise exceptions.UserError(
                                _(
                                    "Centre non trouvé %s (ligne de commande %s)"
                                )
                                % (poste.display_name, line.display_name)
                        )
                        else:
                            raise exceptions.UserError(
                                _(
                                    "Centre non unique pour le poste %s (ligne de commande %s)"
                                )
                                % (poste.display_name, line.display_name)
                            )   

        if not center:
            return

        # 3) Application de la distribution analytique (100% sur (center, poste))
        key = f"{center.id},{poste.id}"
        analytic_map = {key: 100}
        line.analytic_distribution = analytic_map

    def _gainde_compute_analytic_distribution(self):
        """Calcule et applique l'analytic_distribution sur les lignes de PO."""

        for order in self:
            for line in order.order_line:
                order._gainde_compute_analytic_distribution_for_line(line)

    # ------------------------------------------------------------
    # CONTROLE SIMPLE MONTANT / OFFRES ALTERNATIVES
    # ------------------------------------------------------------

    def _compute_gainde_amount_blocked(self):
        """Calcule si la commande serait bloquée par les règles montant/offres.

        Règles:
        - Si achat urgent (is_urgent_purchase) -> jamais bloqué.
        - Sinon, si montant HT <= 200 000 -> pas de blocage.
        - Sinon, si montant HT > 200 000 et moins de 3 offres
          alternatives (alternative_po_ids) -> bloqué.
        """

        for order in self:
            is_urgent = bool(getattr(order, "is_urgent_purchase", False))
            alternative_pos = getattr(order, "alternative_po_ids", self.env["purchase.order"])
            alt_count = len(alternative_pos)
            amount = order.amount_untaxed or 0.0

            blocked = False
            if not is_urgent and amount > 200000:
                # Entre 200 000 et 5 000 000 : au moins 3 offres
                if amount <= 5000000 and alt_count < 3:
                    blocked = True
                # Au-delà de 5 000 000 : besoin de 3 offres ET d'un TDR lié
                elif amount > 5000000 and (alt_count < 3 or not order.tdr_linked_id):
                    blocked = True

            order.gainde_amount_blocked = blocked

    def fields_get(self, allfields=None, attributes=None):
        """Ajuste le libellé de l'état *sent* en *A valider*.

        On ne change pas les valeurs techniques des états, seulement
        l'étiquette affichée à l'utilisateur pour la valeur 'sent'.
        """

        res = super().fields_get(allfields=allfields, attributes=attributes)
        state_info = res.get("state")
        if state_info and state_info.get("selection"):
            new_selection = []
            for key, label in state_info["selection"]:
                if key == "sent":
                    label = "A valider"
                new_selection.append((key, label))
            state_info["selection"] = new_selection
        return res

    def _gainde_check_simple_amount_rules(self):
        """Applique les règles métiers simples au moment de la confirmation.

        - Si achat urgent (is_urgent_purchase) -> aucune vérification.
        - Sinon, si montant HT <= 200 000 -> aucune vérification.
        - Sinon, si montant HT > 200 000 et moins de 3 offres
          alternatives (alternative_po_ids) -> blocage avec message.
        """

        for order in self:
            is_urgent = bool(getattr(order, "is_urgent_purchase", False))
            if is_urgent:
                continue

            amount = order.amount_untaxed or 0.0
            if amount <= 200000:
                # En dessous de 200 000 : aucune contrainte
                continue

            alternative_pos = getattr(order, "alternative_po_ids", self.env["purchase.order"])
            alt_count = len(alternative_pos)

            # 200 000 < montant <= 5 000 000 : au moins 3 offres
            if 200000 < amount <= 5000000:
                if alt_count < 3:
                    raise UserError(
                        _(
                            "Confirmation refusée.\n\n"
                            "Montant HT de la commande: %(amount).2f (entre 200 000 et 5 000 000).\n"
                            "Nombre d'offres alternatives: %(alt)d (minimum requis: 3)."
                        )
                        % {"amount": amount, "alt": alt_count}
                    )
                continue

            # Montant > 5 000 000 : besoin de 3 offres ET d'un TDR lié
            if amount > 5000000:
                if alt_count < 3:
                    raise UserError(
                        _(
                            "Confirmation refusée.\n\n"
                            "Montant HT de la commande: %(amount).2f (supérieur à 5 000 000).\n"
                            "Nombre d'offres alternatives: %(alt)d (minimum requis: 3)."
                        )
                        % {"amount": amount, "alt": alt_count}
                    )

                if not order.tdr_linked_id:
                    raise UserError(
                        _(
                            "Confirmation refusée.\n\n"
                            "Pour une commande dépassant 5 000 000, un TDR doit être créé "
                            "et lié à la commande."
                        )
                    )

    # ------------------------------------------------------------
    # CONTROLE DEPASSEMENT BUDGET (is_above_budget)
    # ------------------------------------------------------------

    def _gainde_check_budget_overrun(self):
        """Bloque si la commande dépasse le budget, sauf dérogation explicite.

        Règle:
        - Si ``is_out_of_budget_limit`` est coché -> on ne bloque pas.
        - Sinon, si ``is_above_budget`` est vrai -> blocage avec message.
        """

        for order in self:
            if order.is_out_of_budget_limit:
                # Dérogation explicite : on laisse passer.
                continue

            # ``is_above_budget`` est fourni par le module account_budget.
            if getattr(order, "is_above_budget", False):
                raise UserError(
                    _(
                        "Confirmation refusée.\n\n"
                        "Cette commande dépasse le budget alloué.\n"
                        "Si vous souhaitez procéder malgré tout, cochez la case \"Est un achat hors budget\"."
                    )
                )

    def action_request_approval(self):
        """Conservée pour compatibilité éventuelle, ne fait plus rien."""
        return True

    def write(self, vals):
        """Met à jour la route d'approbation si la société change.

        Si company_id est modifiée et qu'aucune approval_route_id n'est
        fournie, on cherche la route par défaut pour la nouvelle société
        (en respectant le flag use_approval_route_purchase si présent).
        """

        if "company_id" in vals and "approval_route_id" not in vals:
            for rec in self:
                company = self.env["res.company"].browse(vals.get("company_id"))
                if getattr(company, "use_approval_route_purchase", False) and not rec.approval_route_id:
                    route = rec._get_default_approval_route_for_order(company)
                    if route:
                        super(PurchaseGaindePurchaseOrder, rec).write({
                            "approval_route_id": route.id
                        })

        return super(PurchaseGaindePurchaseOrder, self).write(vals)

    def action_open_tdr(self):
        """Ouvre ou crée le TDR lié à cette commande d'achat.

        - Si un TDR est déjà lié (tdr_linked_id), on ouvre sa fiche.
        - Sinon, on crée un TDR de base et on le lie, puis on ouvre la fiche.
        """

        self.ensure_one()
        PurchaseTdr = self.env["purchase.tdr"]

        if self.tdr_linked_id:
            tdr = self.tdr_linked_id
        else:
            vals = {
                "name": self.name or _("TDR %s") % self.id,
                "date": fields.Date.context_today(self),
            }
            tdr = PurchaseTdr.create(vals)
            self.tdr_linked_id = tdr.id

        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase_gainde.action_purchase_tdr"
        )
        action.update(
            {
                "view_mode": "form",
                "res_id": tdr.id,
                "views": [
                    (
                        self.env.ref("purchase_gainde.view_purchase_tdr_form").id,
                        "form",
                    )
                ],
            }
        )
        return action

    def button_confirm(self):
        # Vérifie d'abord les règles montant/offres simples
        self._gainde_check_simple_amount_rules()
        # Puis contrôle le dépassement budgétaire (is_above_budget),
        # avec possibilité de dérogation via is_out_of_budget_limit
        self._gainde_check_budget_overrun()
        return super(PurchaseGaindePurchaseOrder, self).button_confirm()


class PurchaseGaindePurchaseOrderLine(models.Model):
    _inherit = ["purchase.order.line"]

    can_edit_analytic_distribution_da = fields.Boolean(
        string="Can Edit Analytic Distribution (DA)",
        compute="_compute_can_edit_analytic_distribution_da",
        store=False,
    )

    def _compute_can_edit_analytic_distribution_da(self):
        current_user = self.env.user
        can_edit = bool(getattr(current_user, "has_profile_rcg", False))
        for line in self:
            line.can_edit_analytic_distribution_da = can_edit
    

    @api.onchange("product_id")
    def _gainde_onchange_product_id_compute_analytic(self):
        """Recalcule la distribution analytique dès la sélection du produit.

        Cela permet d'avoir le même comportement que sur les lignes de
        demande d'achat, directement lors du choix du produit dans le
        dropdown de la commande d'achat.
        """

        for line in self:
            order = line.order_id
            if not order or not line.product_id:
                continue
            # On laisse remonter les UserError éventuelles (poste manquant,
            # centre introuvable ou non unique), comme sur les PR.
            order._gainde_compute_analytic_distribution_for_line(line)

    @api.model_create_multi
    def create(self, vals_list):
        lines = super(PurchaseGaindePurchaseOrderLine, self).create(vals_list)
        orders = lines.mapped("order_id")
        orders._gainde_compute_analytic_distribution()
        return lines

    def write(self, vals):
        res = super(PurchaseGaindePurchaseOrderLine, self).write(vals)
        # Ne relancer le recalcul analytique que si le produit change.
        # Évite de déclencher _gainde_compute_analytic_distribution sur les
        # mises à jour de prix/devise (onchange partner_id) qui causent une
        # UserError non gérée → UncaughtPromiseError côté JS.
        if "product_id" in vals:
            orders = self.mapped("order_id")
            orders._gainde_compute_analytic_distribution()
        return res
