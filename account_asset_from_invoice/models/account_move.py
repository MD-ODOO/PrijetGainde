from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    can_create_asset = fields.Boolean(
        compute="_compute_can_create_asset",
        store=False
    )

    @api.depends("invoice_line_ids.account_id.code")
    def _compute_can_create_asset(self):
        for move in self:
            move.can_create_asset = any(
                line.account_id
                and line.account_id.code
                and line.account_id.code.startswith("2")
                for line in move.invoice_line_ids
            )

    def action_create_asset(self):
        self.ensure_one()
        Asset = self.env["account.asset"]
        created_assets = []

        for move in self:
            # uniquement factures fournisseurs postées
            if move.move_type != "in_invoice" or move.state != "posted":
                continue

            for line in move.line_ids:
                # uniquement lignes avec montant
                if not line.balance:
                    continue

                # uniquement comptes de classe 2
                if not line.account_id.code or not line.account_id.code.startswith("2"):
                    continue

                # anti-doublon natif
                existing = Asset.search(
                    [("original_move_line_ids", "in", [line.id])],
                    limit=1,
                )
                if existing:
                    continue

                amount = abs(line.balance)

                asset = Asset.create({
                    "name": line.name or move.name,
                    "original_value": amount,
                    "acquisition_date": move.invoice_date,
                    "state": "draft",
                    "original_move_line_ids": [(6, 0, [line.id])],
                    # 🔗 lien vers la facture (champ studio)
                    "x_studio_many2one_field_9hv_1jch0ma7q": move.id,
                })

                created_assets.append(asset.id)

        # ouverture automatique de la fiche immobilisation
        if created_assets:
            action = {
                "type": "ir.actions.act_window",
                "name": "Immobilisation",
                "res_model": "account.asset",
                "view_mode": "form",
                "res_id": created_assets[0],
                "target": "current",
            }
            return action
        return True