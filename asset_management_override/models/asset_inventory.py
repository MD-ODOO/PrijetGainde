from odoo import models, fields, api, _


class AssetInventory(models.Model):
    _name = "asset.inventory"
    _description = "Session d'inventaire des actifs"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_start desc, id desc"

    name = fields.Char(
        string="Référence",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nouveau"),
        tracking=True,
    )
    date_start = fields.Date(
        string="Date de début",
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    date_end = fields.Date(string="Date de fin", tracking=True)
    state = fields.Selection(
        [("draft", "Brouillon"), ("in_progress", "En cours"), ("done", "Terminé")],
        string="État",
        default="draft",
        readonly=True,
        tracking=True,
    )
    operator_id = fields.Many2one(
        "res.users",
        string="Opérateur",
        default=lambda self: self.env.user,
        required=True,
    )
    notes = fields.Text(string="Notes")
    line_ids = fields.One2many("asset.inventory.line", "inventory_id", string="Actifs scannés")

    # Champ de scan — alimenté par scanner USB/Bluetooth ou saisie manuelle
    barcode_scan = fields.Char(string="Scanner un code-barres", store=False)

    # Statistiques
    scanned_count = fields.Integer(compute="_compute_stats", string="Scannés")
    unexpected_count = fields.Integer(compute="_compute_stats", string="Inattendus")
    missing_count = fields.Integer(compute="_compute_stats", string="Manquants")

    @api.depends("line_ids", "line_ids.state", "line_ids.asset_id")
    def _compute_stats(self):
        all_active_ids = set(
            self.env["asset.management"].search([("status", "!=", "destroyed")]).ids
        )
        for inv in self:
            found_ids = set(
                inv.line_ids.filtered(lambda l: l.state == "found").mapped("asset_id").ids
            )
            inv.scanned_count = len(found_ids)
            inv.unexpected_count = len(inv.line_ids.filtered(lambda l: l.state == "unexpected"))
            inv.missing_count = len(all_active_ids - found_ids)

    @api.onchange("barcode_scan")
    def _onchange_barcode_scan(self):
        if not self.barcode_scan:
            return
        barcode = self.barcode_scan
        self.barcode_scan = False

        asset = self.env["asset.management"].search([("barcode", "=", barcode)], limit=1)
        if not asset:
            return {
                "warning": {
                    "title": _("Barcode inconnu"),
                    "message": _("Aucun actif trouvé pour le code : %s") % barcode,
                }
            }

        if asset.status == "destroyed":
            return {
                "warning": {
                    "title": _("Actif sorti"),
                    "message": _('"%s" est en statut Sorti et ne fait pas partie de l\'inventaire.') % asset.name,
                }
            }

        if any(l.asset_id.id == asset.id for l in self.line_ids):
            return {
                "warning": {
                    "title": _("Doublon"),
                    "message": _('"%s" est déjà dans l\'inventaire.') % asset.name,
                }
            }

        new_line = self.env["asset.inventory.line"].new({
            "asset_id": asset.id,
            "barcode": barcode,
            "state": "found",
            "scan_date": fields.Datetime.now(),
        })
        self.line_ids |= new_line

    def action_scan_barcode(self, barcode):
        """Appelé depuis le handler JS — crée directement une ligne en base."""
        self.ensure_one()
        asset = self.env["asset.management"].search([("barcode", "=", barcode)], limit=1)
        if not asset:
            return {"status": "not_found", "barcode": barcode}
        if asset.status == "destroyed":
            return {"status": "destroyed", "name": asset.name}
        if self.line_ids.filtered(lambda l: l.asset_id == asset):
            return {"status": "duplicate", "name": asset.name}
        self.env["asset.inventory.line"].create({
            "inventory_id": self.id,
            "asset_id": asset.id,
            "barcode": barcode,
            "state": "found",
            "scan_date": fields.Datetime.now(),
        })
        return {"status": "found", "name": asset.name}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nouveau"):
                vals["name"] = self.env["ir.sequence"].next_by_code("asset.inventory") or _("Nouveau")
        return super().create(vals_list)

    def action_start(self):
        self.write({"state": "in_progress"})

    def action_done(self):
        self.write({"state": "done", "date_end": fields.Date.today()})

    def action_reset_draft(self):
        self.write({"state": "draft"})

    def action_print_report(self):
        return self.env.ref(
            "asset_management_override.action_report_asset_inventory"
        ).report_action(self)

    def action_open_mobile_scan(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/asset-inventory/scan?session_id={self.id}",
            "target": "new",
        }

    def _get_missing_assets(self):
        """Retourne les actifs actifs non trouvés lors de cet inventaire."""
        self.ensure_one()
        all_active = self.env["asset.management"].search([("status", "!=", "destroyed")])
        scanned_ids = self.line_ids.filtered(lambda l: l.state == "found").mapped("asset_id").ids
        return all_active.filtered(lambda a: a.id not in scanned_ids)


class AssetInventoryLine(models.Model):
    _name = "asset.inventory.line"
    _description = "Ligne d'inventaire d'actif"
    _order = "scan_date desc"

    inventory_id = fields.Many2one(
        "asset.inventory",
        string="Inventaire",
        required=True,
        ondelete="cascade",
    )
    asset_id = fields.Many2one("asset.management", string="Actif")
    barcode = fields.Char(string="Code-barres scanné")
    scan_date = fields.Datetime(string="Date de scan", default=fields.Datetime.now)
    state = fields.Selection(
        [("found", "Trouvé"), ("unexpected", "Inattendu")],
        string="État",
        default="found",
    )

    # Champs relationnels pour affichage
    asset_name = fields.Char(related="asset_id.name", string="Nom de l'actif", store=False)
    invoice_date = fields.Date(
        related="asset_id.invoice_date", string="Date d'acquisition", store=False
    )
    localisation_id = fields.Many2one(
        related="asset_id.localisation", string="Localisation", store=False
    )
    assigne_a = fields.Many2one(
        related="asset_id.assigne_a", string="Assigné à", store=False
    )
