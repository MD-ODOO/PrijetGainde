import os

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _is_admin_user(self):
        return self.env.is_superuser() or self.env.user.has_group("base.group_system")

    def _allowed_extensions(self):
        param = self.env["ir.config_parameter"].sudo().get_param(
            "purchase_gainde.allowed_attachment_extensions"
        )
        if param:
            return {
                ext.strip().lower().lstrip(".")
                for ext in param.split(",")
                if ext.strip()
            }
        return {
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "csv",
            "txt",
            "xml",
            "js",
            "css",
            "po",
            "pot",
            "svg",
            "json",
            "yml",
            "yaml",
            "zip",
            "jpg",
            "jpeg",
            "png",
            "gif",
            "bmp",
            "tif",
            "tiff",
            "odt",
            "ods",
        }

    def _should_skip_extension_check(self, filename, res_model=None):
        if not filename:
            return True
        if (
            self.env.context.get("install_mode")
            or self.env.context.get("module")
            or self.env.context.get("module_install")
            or self.env.context.get("update_module")
        ):
            return True
        internal_models = {
            "ir.ui.menu",
            "ir.ui.view",
            "ir.ui.icon",
            "ir.actions.act_window",
            "ir.actions.server",
        }
        if res_model in internal_models:
            return True
        if res_model and res_model.startswith("ir."):
            return True
        return False

    def _check_extension_allowed(self, filename, res_model=None):
        if self._should_skip_extension_check(filename, res_model=res_model):
            return True

        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if not ext:
            return True
        if not ext or ext not in self._allowed_extensions():
            raise UserError(
                _(
                    "Type de fichier non autorisé (%s). Extensions permises : %s"
                )
                % (ext or "(aucune)", ", ".join(sorted(self._allowed_extensions())))
            )
        return True

    def _check_upload_rights(self, vals):
        if self._is_admin_user():
            return

        res_model = vals.get("res_model")
        res_id = vals.get("res_id")
        if not res_model:
            raise AccessError(
                _(
                    "Vous n'êtes pas autorisé à uploader une pièce jointe sans document lié."
                )
            )

        record = False
        if res_id:
            record = self.env[res_model].browse(res_id)

        if record and record.exists():
            record.check_access_rights("write")
            record.check_access_rule("write")
        else:
            model = self.env[res_model]
            model.check_access_rights("create")

    @api.model
    def create(self, vals):
        filename = vals.get("datas_fname") or vals.get("name")
        if vals.get("type", "binary") == "binary" and vals.get("datas"):
            self._check_extension_allowed(filename, res_model=vals.get("res_model"))
            self._check_upload_rights(vals)
        return super().create(vals)

    def write(self, vals):
        if vals.get("type", "binary") == "binary" and ("datas" in vals or "datas_fname" in vals):
            filename = vals.get("datas_fname") or vals.get("name")
            if not filename and self:
                if "datas_fname" in self[0]._fields:
                    filename = self[0].datas_fname or self[0].name
                else:
                    filename = self[0].name
            if filename:
                res_model = vals.get("res_model") or (self[0].res_model if self else None)
                self._check_extension_allowed(filename, res_model=res_model)

        if "res_model" in vals or "res_id" in vals or "datas" in vals:
            for attachment in self:
                self._check_upload_rights({
                    "res_model": vals.get("res_model") or attachment.res_model,
                    "res_id": vals.get("res_id") or attachment.res_id,
                })

        return super().write(vals)

    def _can_read_attachment(self, attachment):
        if self._is_admin_user():
            return True

        if attachment.create_uid == self.env.user:
            return True

        if attachment.res_model and attachment.res_id:
            record = self.env[attachment.res_model].browse(attachment.res_id)
            if record.exists():
                try:
                    record.check_access_rights("read")
                    record.check_access_rule("read")
                    return True
                except Exception:
                    return False
        return False

    @api.model
    def search(self, domain=None, offset=0, limit=None, order=None):
        records = super().search(domain, offset=offset, limit=limit, order=order)
        if self._is_admin_user():
            return records
        return records.filtered(self._can_read_attachment)

    def read(self, fields=None, load="_classic_read"):
        if not self._is_admin_user():
            for attachment in self:
                if not self._can_read_attachment(attachment):
                    raise AccessError(_("Vous n'avez pas accès à cette pièce jointe."))
        return super().read(fields=fields, load=load)
