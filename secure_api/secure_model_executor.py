import odoo
from odoo.service import model
from odoo.exceptions import UserError
from odoo.tools.translate import _
from odoo.release import version_info  # (18, ...)

import logging

_logger = logging.getLogger(__name__)


class SecureModelExecutor:
    """Custom execution wrapper for database operations."""

    _original_execute = None

    @classmethod
    def wrap_execute(cls, new_execute):
        """Wrap the original model.execute_cr function."""
        if cls._original_execute is None:
            cls._original_execute = model.execute_cr
            model.execute_cr = new_execute
            _logger.info("Successfully wrapped odoo.service.model.execute_cr")

    @classmethod
    def restore_original(cls):
        """Restore the original execute_cr function if needed."""
        if cls._original_execute:
            model.execute_cr = cls._original_execute
            _logger.info("Restored original odoo.service.model.execute_cr")


def is_rpc_allowed(cr):
    is_disable_xml_rpc = False
    if version_info[0] >= 17:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
        is_disable_xml_rpc = env["ir.config_parameter"].sudo().get_param("secure_api.is_disable_xml_rpc")
        _logger.info(f"secure_api.is_disable_xml_rpc ({is_disable_xml_rpc})")
    else:
        with odoo.api.Environment.manage():
            env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
            is_disable_xml_rpc = env["ir.config_parameter"].sudo().get_param("secure_api.is_disable_xml_rpc")
            _logger.info(f"secure_api.is_disable_xml_rpc ({is_disable_xml_rpc})")
    return not is_disable_xml_rpc


def secure_execute_cr(cr, uid, obj, method, *args, **kw):
    if not is_rpc_allowed(cr):
        raise UserError(_("XML-RPC is disabled by Secure API. You are not allowed to call this object %s", obj))
    return SecureModelExecutor._original_execute(cr, uid, obj, method, *args, **kw)


def _secure_model_exe():
    """Hook function to wrap execute_cr after module load."""
    SecureModelExecutor.wrap_execute(secure_execute_cr)


def uninstall_hook(cr, registry):
    SecureModelExecutor.restore_original()

