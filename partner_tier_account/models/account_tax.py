from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_lines(self, base_lines, company, tax_lines=None):
        res = super()._prepare_tax_lines(base_lines, company, tax_lines=tax_lines)

        move = self._get_brs_move_from_base_lines(base_lines)
        if not move or move.move_type != "in_invoice":
            return res

        partner = move.partner_id
        if not partner or "cofi" not in partner._fields:
            return res
        cofi = (partner.cofi or "").strip()
        if not cofi or cofi[0] != "1":
            return res

        def invert_if_brs(tax_rep_line, amounts):
            tax = tax_rep_line.tax_id if tax_rep_line else False
            if not self._is_brs_withholding_tax(tax):
                return
            if "amount_currency" in amounts:
                amounts["amount_currency"] = -amounts["amount_currency"]
            if "balance" in amounts:
                amounts["balance"] = -amounts["balance"]

        for tax_line_vals in res.get("tax_lines_to_add", []):
            tax_rep_line = self.env["account.tax.repartition.line"].browse(
                tax_line_vals.get("tax_repartition_line_id")
            )
            invert_if_brs(tax_rep_line, tax_line_vals)

        for tax_line, _grouping_key, amounts in res.get("tax_lines_to_update", []):
            invert_if_brs(tax_line.tax_repartition_line_id, amounts)

        return res

    @staticmethod
    def _get_brs_move_from_base_lines(base_lines):
        for base_line in base_lines:
            record = base_line.get("record")
            if record and getattr(record, "move_id", False):
                return record.move_id
        return False

    @staticmethod
    def _is_brs_withholding_tax(tax):
        if not tax:
            return False
        name = (tax.name or "").lower().replace(" ", "")
        group_name = (tax.tax_group_id.name or "").lower()
        if "brs" in group_name or "brs" in name:
            return True
        if tax.amount_type == "percent" and abs(tax.amount - 5.0) < 0.0001:
            return True
        return "5%t" in name or "5%s" in name
