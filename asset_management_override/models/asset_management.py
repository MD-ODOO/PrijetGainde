import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AssetManagementOverride(models.Model):
    _name = "asset.management"
    _inherit = ["asset.management", "mail.thread"]
    _sql_constraints = [
        ("asset_management_barcode_unique", "unique(barcode)", "Le code-barres doit être unique."),
    ]

    _barcode_prefix_letter = "G"

    status = fields.Selection(
        [
            ("draft", "Brouillon"),
            ("assign", "Affecté"),
            ("return", "Retour"),
            ("on_hold", "En attente"),
            ("in_warehouse", "Disponible"),
            ("repair", "Maintenance"),
            ("destroyed", "Sortie"),
        ],
        string="Status",
        default="assign",
        tracking=True,
    )

    brand = fields.Char(string="Marque", tracking=True)
    asset_model = fields.Char(string="Modèle", tracking=True)

    vendor_id = fields.Many2one(
        "asset.vendor",
        string="Associated Vendor",
        ondelete="set null",
    )

    date_reception = fields.Date(
        string="Date de réception",
        help="Date de réception de l'actif",
        tracking=True,
    )

    account_asset_id = fields.Many2one(
        "account.asset",
        string="Actif comptable",
        help="Lien vers l'actif comptable correspondant",
        ondelete="set null",
        tracking=True,
    )

    book_value = fields.Monetary(
        string="Valeur comptable actuelle",
        compute="_compute_book_value",
        currency_field="currency_id",
        help="Valeur nette comptable issue de l'actif comptable lié (amortissements déduits)",
    )

    currency_id = fields.Many2one(
        "res.currency",
        compute="_compute_book_value",
    )

    def _compute_book_value(self):
        for asset in self:
            aa = asset.account_asset_id
            asset.book_value = aa.book_value if aa else 0.0
            asset.currency_id = aa.currency_id if aa else self.env.company.currency_id

    amount = fields.Float(
        string="Coût d'achat",
        help="Coût d'achat de l'actif",
    )

    invoice_date = fields.Date(
        string="Acquis le",
        help="Date d'acquisition de l'actif",
    )

    document_ids = fields.Many2many(
        "ir.attachment",
        string="Pièces jointes",
        help="Télécharger plusieurs documents liés à l'actif (ex: Garantie, Facture)",
    )

    assigne_a = fields.Many2one(
        "hr.employee",
        string="Affecté à",
        help="Employé à qui l'actif est affecté",
        tracking=True,
    )

    date_assignation = fields.Date(
        string="Date d'affectation",
        help="Date à laquelle l'actif a été affecté",
        tracking=True,
    )

    assigne_par = fields.Many2one(
        "res.users",
        string="Affecté par",
        help="Utilisateur qui a effectué l'affectation",
        default=lambda self: self.env.user,
        tracking=True,
    )

    localisation = fields.Many2one(
        "asset.localisation",
        string="Localisation",
        help="Localisation de l'actif",
        tracking=True,
    )

    maintenance_request_id = fields.Many2one(
        "maintenance.request",
        string="Demande de maintenance",
        help="Demande de maintenance liée à cet actif",
        ondelete="set null",
        tracking=True,
    )

    def _register_hook(self):
        """Keep DB schema in sync for legacy databases missing this column."""
        res = super()._register_hook()
        self.env.cr.execute(
            """
            ALTER TABLE asset_management
            ADD COLUMN IF NOT EXISTS maintenance_request_id integer
            """
        )
        return res

    # ----------------------------------------------------------
    # Onchange
    # ----------------------------------------------------------

    @api.onchange("assigne_a")
    def _onchange_assigne_a(self):
        if self.assigne_a:
            self.status = "assign"
        else:
            self.status = "in_warehouse"

    @api.onchange("asset_type_id")
    def _onchange_asset_type_id(self):
        if self.asset_type_id and self.status == "draft":
            self.status = "in_warehouse"

    def _compute_name_from_brand_model(self):
        """Retourne le nom à partir de Marque + Modèle, ou None si les deux sont vides."""
        parts = [p for p in [self.brand, self.asset_model] if p and p.strip()]
        return " ".join(parts) if parts else None

    @api.onchange("brand", "asset_model")
    def _onchange_brand_model(self):
        name = self._compute_name_from_brand_model()
        if name:
            self.name = name

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id and not self._compute_name_from_brand_model():
            self.name = self.product_id.name

    @api.onchange("invoice_id")
    def _onchange_invoice_id(self):
        if self.invoice_id:
            self.amount = self.invoice_id.amount_total
            self.invoice_date = self.invoice_id.invoice_date

    @api.onchange("account_asset_id")
    def _onchange_account_asset_id(self):
        """Pré-remplir les champs depuis l'actif comptable lié."""
        if self.account_asset_id:
            aa = self.account_asset_id
            if aa.original_value and not self.amount:
                self.amount = aa.original_value
            if aa.acquisition_date and not self.invoice_date:
                self.invoice_date = aa.acquisition_date
            if aa.name and not self.name:
                self.name = aa.name

    # ----------------------------------------------------------
    # Notifications comptabilité
    # ----------------------------------------------------------

    def _get_accounting_partner_ids(self):
        partner_ids = set()
        for xmlid in ("account.group_account_user", "account.group_account_manager"):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if not group:
                continue
            self.env.cr.execute(
                """SELECT u.partner_id FROM res_users u
                   JOIN res_groups_users_rel r ON r.uid = u.id
                   WHERE r.gid = %s AND u.active = true""",
                (group.id,),
            )
            partner_ids.update(row[0] for row in self.env.cr.fetchall() if row[0])
        return list(partner_ids)

    def _notify_accounting(self, body):
        partner_ids = self._get_accounting_partner_ids()
        if not partner_ids:
            return False
        for asset in self:
            asset.message_post(
                body=body,
                partner_ids=partner_ids,
                subtype_xmlid="mail.mt_comment",
            )
        return True

    def _format_asset_name(self):
        self.ensure_one()
        return self.display_name or self.name or ""

    # ----------------------------------------------------------
    # Génération / validation code-barres
    # ----------------------------------------------------------

    def _get_barcode_prefix(self, asset_type):
        code = asset_type.account_immo.code if asset_type and asset_type.account_immo else ""
        digits = re.sub(r"\D", "", code or "")
        if len(digits) < 4:
            return False
        return f"{self._barcode_prefix_letter}{digits[:4]}"

    def _get_next_barcode_sequence(self, prefix):
        max_seq = 0
        barcodes = self.search([("barcode", "ilike", prefix)]).mapped("barcode")
        target_len = len(prefix) + 3
        for barcode in barcodes:
            if (
                barcode
                and barcode.startswith(prefix)
                and len(barcode) == target_len
                and barcode[-3:].isdigit()
            ):
                max_seq = max(max_seq, int(barcode[-3:]))
        return max_seq + 1

    def _generate_barcode(self, asset_type):
        prefix = self._get_barcode_prefix(asset_type)
        if not prefix:
            raise ValidationError(
                _("Compte immobilisation invalide pour générer le code-barres.")
            )
        next_seq = self._get_next_barcode_sequence(prefix)
        return f"{prefix}{next_seq:03d}"

    def _validate_barcode(self, barcode, asset_type):
        prefix = self._get_barcode_prefix(asset_type)
        if not prefix:
            raise ValidationError(
                _("Compte immobilisation invalide pour générer le code-barres.")
            )
        expected_len = len(prefix) + 3
        if (
            not barcode
            or not barcode.startswith(prefix)
            or len(barcode) != expected_len
            or not barcode[-3:].isdigit()
        ):
            raise ValidationError(
                _("Code-barres invalide. Format attendu : %sXXX") % prefix
            )
        return True

    @api.constrains("barcode")
    def _check_barcode_unique(self):
        for asset in self:
            if asset.barcode:
                if (
                    self.search_count(
                        [("barcode", "=", asset.barcode), ("id", "!=", asset.id)]
                    )
                    > 0
                ):
                    raise ValidationError(_("Le code-barres doit être unique."))
            if asset.barcode and asset.asset_type_id and asset.asset_type_id.account_immo:
                asset._validate_barcode(asset.barcode, asset.asset_type_id)

    # ----------------------------------------------------------
    # Synchronisation transferts et actif comptable
    # ----------------------------------------------------------

    def _sync_transfer_from_affectation(self, vals):
        """Synchroniser les champs d'affectation avec transfer_ids."""
        affectation_fields = ['assigne_a', 'date_assignation', 'assigne_par', 'localisation']
        if not any(field in vals for field in affectation_fields):
            return

        assigne_a = vals.get('assigne_a', self.assigne_a.id if self.assigne_a else False)
        date_assignation = vals.get('date_assignation', self.date_assignation if self else False)
        assigne_par = vals.get('assigne_par', self.assigne_par.id if self.assigne_par else False)
        localisation = vals.get('localisation', self.localisation.id if self.localisation else False)

        if not assigne_a:
            return

        assigne_a_changed = False
        if self and self.id and 'assigne_a' in vals:
            old_assigne_a = self.assigne_a.id if self.assigne_a else False
            assigne_a_changed = old_assigne_a != assigne_a

        last_transfer = self.transfer_ids.sorted(key=lambda t: t.id, reverse=True)[:1] if self.transfer_ids else False

        if last_transfer and not assigne_a_changed and 'assigne_a' not in vals:
            transfer_vals = {}
            if 'date_assignation' in vals and date_assignation:
                transfer_vals['assign_date'] = date_assignation
            if 'assigne_par' in vals and assigne_par:
                transfer_vals['assign_by'] = assigne_par
            if 'localisation' in vals:
                transfer_vals['localisation'] = localisation
            if transfer_vals:
                last_transfer.write(transfer_vals)
        else:
            transfer_vals = {
                'asset_id': self.id,
                'transfer_employee_id': assigne_a,
                'assign_date': date_assignation,
                'assign_by': assigne_par,
                'localisation': localisation,
            }
            self.env['asset.transfer.entry'].create(transfer_vals)

    def _sync_to_account_asset(self, vals):
        """Synchroniser les champs clés de l'actif immobilisé vers l'actif comptable."""
        if not self.account_asset_id:
            return
        sync_map = {
            "name": "name",
            "barcode": "barcode",
        }
        account_vals = {
            acc_field: vals[am_field]
            for am_field, acc_field in sync_map.items()
            if am_field in vals
        }
        # Si account_asset_id vient d'être lié, on pousse le barcode existant
        if "account_asset_id" in vals and self.barcode and "barcode" not in account_vals:
            account_vals["barcode"] = self.barcode
        if not account_vals:
            return
        try:
            self.account_asset_id.write(account_vals)
        except Exception:
            pass

    # ----------------------------------------------------------
    # ORM
    # ----------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                brand = vals.get("brand", "").strip() if vals.get("brand") else ""
                model = vals.get("asset_model", "").strip() if vals.get("asset_model") else ""
                parts = [p for p in [brand, model] if p]
                if parts:
                    vals["name"] = " ".join(parts)
                elif vals.get("product_id"):
                    product = self.env["product.product"].browse(vals["product_id"])
                    if product:
                        vals["name"] = product.name

            if "assigne_a" in vals:
                vals["status"] = "assign" if vals["assigne_a"] else "in_warehouse"

            asset_type = False
            if vals.get("asset_type_id"):
                asset_type = self.env["asset.type"].browse(vals["asset_type_id"])
            if vals.get("barcode"):
                if asset_type and asset_type.account_immo:
                    self._validate_barcode(vals["barcode"], asset_type)
            else:
                if asset_type and asset_type.account_immo:
                    vals["barcode"] = self._generate_barcode(asset_type)

        records = super().create(vals_list)

        for asset in records:
            if not asset.barcode and asset.asset_type_id and asset.asset_type_id.account_immo:
                asset.barcode = asset._generate_barcode(asset.asset_type_id)

        for asset in records:
            if asset.barcode and asset.account_asset_id:
                try:
                    asset.account_asset_id.write({"barcode": asset.barcode})
                except Exception:
                    pass

        for asset in records:
            asset._notify_accounting(
                _("Nouvel actif créé : %s") % asset._format_asset_name()
            )

        for i, asset in enumerate(records):
            asset._sync_transfer_from_affectation(vals_list[i])

        return records

    def write(self, vals):
        if "assigne_a" in vals:
            vals["status"] = "assign" if vals["assigne_a"] else "in_warehouse"

        if "asset_type_id" in vals and vals["asset_type_id"]:
            for asset in self:
                if asset.status == "draft":
                    vals["status"] = "in_warehouse"
                    break

        if "brand" in vals or "asset_model" in vals or "product_id" in vals:
            for asset in self:
                brand = vals.get("brand", asset.brand or "")
                model = vals.get("asset_model", asset.asset_model or "")
                brand = brand.strip() if brand else ""
                model = model.strip() if model else ""
                parts = [p for p in [brand, model] if p]
                if parts:
                    vals["name"] = " ".join(parts)
                elif vals.get("product_id"):
                    product = self.env["product.product"].browse(vals["product_id"])
                    if product:
                        vals["name"] = product.name
                break

        # Génération / validation du code-barres si barcode ou asset_type change
        if "barcode" in vals or "asset_type_id" in vals:
            processed_vals = {}
            for asset in self:
                asset_vals = dict(vals)
                new_asset_type = asset.asset_type_id
                if asset_vals.get("asset_type_id"):
                    new_asset_type = self.env["asset.type"].browse(asset_vals["asset_type_id"])
                if asset_vals.get("barcode"):
                    if new_asset_type and new_asset_type.account_immo:
                        asset._validate_barcode(asset_vals["barcode"], new_asset_type)
                else:
                    if not asset.barcode and new_asset_type and new_asset_type.account_immo:
                        asset_vals["barcode"] = asset._generate_barcode(new_asset_type)
                processed_vals[asset.id] = asset_vals

            unique_payloads = {tuple(sorted(v.items())) for v in processed_vals.values()}
            if len(unique_payloads) > 1:
                notify_destroyed = "status" in vals and vals.get("status") == "destroyed"
                for asset in self:
                    super(AssetManagementOverride, asset).write(processed_vals[asset.id])
                    asset._sync_to_account_asset(processed_vals[asset.id])
                    asset._sync_transfer_from_affectation(processed_vals[asset.id])
                    if notify_destroyed and asset.status == "destroyed":
                        asset._notify_accounting(
                            _("Actif mis en sortie : %s") % asset._format_asset_name()
                        )
                        if asset.account_asset_id and asset.account_asset_id.state == "open":
                            try:
                                asset.account_asset_id.set_to_close()
                            except Exception:
                                pass
                return True
            vals = processed_vals[self.id]

        notify_destroyed = "status" in vals and vals.get("status") == "destroyed"
        res = super().write(vals)

        for asset in self:
            asset._sync_to_account_asset(vals)
            asset._sync_transfer_from_affectation(vals)
            if notify_destroyed and asset.status == "destroyed":
                asset._notify_accounting(
                    _("Actif mis en sortie : %s") % asset._format_asset_name()
                )
                if asset.account_asset_id and asset.account_asset_id.state == "open":
                    try:
                        asset.account_asset_id.set_to_close()
                    except Exception:
                        pass

        return res

    # ----------------------------------------------------------
    # Navigation vers l'actif comptable
    # ----------------------------------------------------------

    def action_open_account_asset(self):
        self.ensure_one()
        if not self.account_asset_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'name': _('Actif comptable'),
            'res_model': 'account.asset',
            'res_id': self.account_asset_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ----------------------------------------------------------
    # Actions de statut
    # ----------------------------------------------------------

    def action_set_status_assign(self):
        self.write({"status": "assign"})
        return True

    def action_set_status_return(self):
        self.write({"status": "return"})
        return True

    def action_set_status_on_hold(self):
        self.write({"status": "on_hold"})
        return True

    def action_set_status_in_warehouse(self):
        self.write({"status": "in_warehouse"})
        return True

    def action_set_status_repair(self):
        """Ouvrir le wizard pour créer une demande de maintenance."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Créer une demande de maintenance',
            'res_model': 'maintenance.request.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }

    def action_set_status_destroyed(self):
        self.write({"status": "destroyed"})
        return True

    def action_print_label_2x7(self):
        return self.env.ref(
            "asset_management_override.report_asset_template_label_2x7_n"
        ).report_action(self)

    def action_confirm_sortie(self):
        """Afficher une popup de confirmation avant de sortir l'actif."""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmer la sortie',
            'res_model': 'asset.sortie.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_asset_id': self.id},
        }


class AssetTypeOverride(models.Model):
    _inherit = "asset.type"

    account_immo = fields.Many2one(
        "account.account",
        string="Compte immobilisation",
        ondelete="set null",
    )

    # Rendre les champs de dépréciation non obligatoires
    depreciation_frequency = fields.Selection(required=False)
    depreciation_method = fields.Selection(required=False)
    depreciation_basis = fields.Selection(required=False)
