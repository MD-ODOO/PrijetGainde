# Copyright 2024
# License LGPL-3.0 or later

from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class SecureAPIBootstrap(http.Controller):
    """Bootstrap controller to register all published APIs on first call"""
    
    @http.route('/api/bootstrap', auth='none', type='http', csrf=False)
    def register_all_apis(self):
        """Register all published APIs and return status"""
        try:
            published_apis = request.env['secure.api'].search([('state', '=', 'published')])
            
            if published_apis:
                count = 0
                for api_record in published_apis:
                    try:
                        api_record.update_routing_map()
                        count += 1
                        _logger.info(f"[bootstrap] ✓ Registered: {api_record.route}")
                    except Exception as e:
                        _logger.warning(f"[bootstrap] Failed for {api_record.name}: {e}")
                
                message = f"Successfully registered {count}/{len(published_apis)} APIs"
                _logger.info(f"[bootstrap] {message}")
                return message
            else:
                return "No published APIs to register"
        except Exception as e:
            _logger.error(f"[bootstrap] Error: {e}")
            return f"Error: {str(e)}"
