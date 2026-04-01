import logging

from odoo import models, _

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _action_done(self):
        res = super()._action_done()
        for picking in self:
            if picking.picking_type_id.code == "incoming":
                picking._create_assets_from_receipt()
        return res

    def _create_assets_from_receipt(self):
        Asset = self.env["asset.management"]
        AccountAsset = self.env["account.asset"]
        for picking in self:
            for move in picking.move_ids:
                if move.state != "done":
                    continue
                account = move.product_id.property_account_expense_id or move.product_id.categ_id.property_account_expense_categ_id
                account_code = (account.code or "").strip() if account else ""
                account_name = (account.name or "").strip() if account else ""
                if not ((account_code and account_code.startswith("2")) or (account_name and account_name.startswith("2"))):
                    _logger.debug(
                        "[Asset] Skip move %s: account code/name not starting with 2 (%s / %s)",
                        move.display_name,
                        account_code,
                        account_name,
                    )
                    
                    continue
                qty_done = 0.0
                if move.move_line_ids:
                    qty_done = sum(move.move_line_ids.mapped("quantity"))
                qty = qty_done or move.product_uom_qty or getattr(move, "quantity", 0.0) or 0.0
                if qty <= 0:
                    continue
                model_type = "single"
                reference = picking.name or picking.origin or move.reference or ""
                purchase_price = getattr(move, "price_unit", 0.0) or 0.0
                purchase_date = picking.date_done or picking.scheduled_date
                vendor = picking.partner_id
                invoice = False
                purchase = getattr(picking, "purchase_id", False)
                if purchase and purchase.invoice_ids:
                    posted = purchase.invoice_ids.filtered(lambda m: m.state == "posted")
                    invoice = (posted or purchase.invoice_ids)[:1]
                elif getattr(picking, "vendor_bill_id", False):
                    invoice = picking.vendor_bill_id
                invoice_lines = self.env["account.move.line"]
                if invoice and invoice.state == "posted":
                    invoice_lines = invoice.line_ids.filtered(
                        lambda line: not line.display_type and line.product_id == move.product_id
                    )
                    if account:
                        invoice_lines = invoice_lines.filtered(lambda line: line.account_id == account)
                    if not invoice_lines:
                        invoice_lines = invoice.line_ids.filtered(
                            lambda line: not line.display_type and (not account or line.account_id == account)
                        )
                for index in range(int(qty)):
                    vals = {
                        "product_id": move.product_id.id,
                        "model_type": model_type,
                        "initial_stock": 1,
                        "status": "draft",
                        "amount": purchase_price,
                        "invoice_date": purchase_date.date() if purchase_date else False,
                        "invoice_id": invoice.id if invoice else False,
                    }
                    asset = Asset.create(vals)
                    if asset:
                        picking.write({"asset_ids": [(4, asset.id)]})
                        _logger.info(
                            "[Asset] Linked asset %s to picking %s",
                            asset.display_name,
                            picking.name,
                        )
                    account_asset_vals = {
                        "name": asset.name or reference or move.product_id.display_name or picking.name or "",
                        "original_value": purchase_price,
                        "acquisition_date": purchase_date.date() if purchase_date else False,
                        "account_asset_id": account.id if account else False,
                        "barcode": asset.barcode if asset else False,
                    }
                    if invoice_lines:
                        account_asset_vals["original_move_line_ids"] = [(6, 0, invoice_lines.ids)]
                    account_asset = AccountAsset.create(account_asset_vals)
                    
                    # Lier l'asset.management à l'account.asset
                    if asset and account_asset:
                        asset.write({"account_asset_id": account_asset.id})
                    
                    _logger.info(
                        "[Asset] Created account.asset %s from picking %s (move %s) index=%s",
                        account_asset.display_name,
                        picking.name,
                        move.display_name,
                        index + 1,
                    )
                    _logger.info(
                        "[Asset] Created asset %s from picking %s (move %s) index=%s",
                        asset.display_name,
                        picking.name,
                        move.display_name,
                        index + 1,
                    )

