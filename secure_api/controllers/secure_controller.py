# -*- coding: utf-8 -*-
import traceback
import io
import time
import odoo
from odoo.http import request
from .request_handler import RequestHandler

import logging

_logger = logging.getLogger(__name__)


def api_execute(api_id, **kargs):
    # Initialize environment if not already set (for auth="none" routes)
    if not request.env:
        db = request.httprequest.environ.get('HTTP_X_OPENERP_DBNAME') or request.session.db or odoo.tools.config.get('db_name')
        if not db:
            # Try to get database from URL or default config
            databases = odoo.service.db.list_dbs(force=True)
            if databases:
                db = databases[0]
        
        if db:
            registry = odoo.registry(db)
            with registry.cursor() as cr:
                env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
                request.env = env
        else:
            raise Exception("No database specified and no default database found")
    
    api_record = request.env["secure.api"].sudo().browse(api_id)
    start_time = time.time()
    try:
        req_handler = RequestHandler(request, api_record, kargs)
        req_handler.check_security()
        result = req_handler()
        elapsed_time = time.time() - start_time

        if api_record.is_stats and api_record.secure_api_stats_id:
            api_record.secure_api_stats_id.success(request=request, elapsed_time=elapsed_time, result=result)

        return result
    except Exception as e:
        # Capture the exception details and stack trace as a string
        log_stream = io.StringIO()
        traceback.print_exc(file=log_stream)
        error_log = log_stream.getvalue()

        _logger.error(f"{error_log}")
        elapsed_time = time.time() - start_time

        # Rollback database
        if request.env and hasattr(request.env, 'cr'):
            request.env.cr.rollback()

        if api_record.is_stats and api_record.secure_api_stats_id:            
            api_record.secure_api_stats_id.error(request=request, error=error_log, elapsed_time=elapsed_time)
            if request.env and hasattr(request.env, 'cr'):
                request.env.cr.commit()

        raise   # raise original exception
