from . import models
from . import controllers
from . import wizard
from .secure_model_executor import _secure_model_exe, uninstall_hook

import logging
_logger = logging.getLogger(__name__)


def _register_api_routes_at_startup():
    """Register all published API routes at module load time"""
    try:
        import odoo
        if odoo.api.call:  # Only register if API is available
            registry = odoo.modules.registry.Registry('odoo')
            if registry:
                with registry.cursor() as cr:
                    from odoo import api, SUPERUSER_ID
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    
                    # Find all published APIs (state = 'published')
                    published_apis = env['secure.api'].search([('state', '=', 'published')])
                    
                    if published_apis:
                        _logger.info(f"[secure_api] Registering {len(published_apis)} published API routes at startup...")
                        
                        for api_record in published_apis:
                            try:
                                api_record.update_routing_map()
                                _logger.info(f"[secure_api] ✓ Route registered: {api_record.route}")
                            except Exception as e:
                                _logger.warning(f"[secure_api] ✗ Failed to register {api_record.name}: {str(e)}")
                        
                        _logger.info("[secure_api] Startup route registration completed")
                    else:
                        _logger.debug("[secure_api] No published APIs found")
                    
                    cr.commit()
    except Exception as e:
        _logger.debug(f"[secure_api] Startup registration not yet available: {str(e)}")


def post_init_hook(env):
    """Register all published API routes after module installation/upgrade"""
    try:
        # Find all published APIs (state = 'published', not 'active')
        published_apis = env['secure.api'].search([('state', '=', 'published')])
        
        if published_apis:
            _logger.info(f"[secure_api] Post-init: Registering {len(published_apis)} published API routes...")
            
            # Register routes for each published API
            for api_record in published_apis:
                try:
                    api_record.update_routing_map()
                    _logger.info(f"[secure_api] ✓ Post-init registered: {api_record.name} ({api_record.route})")
                except Exception as e:
                    _logger.error(f"[secure_api] ✗ Post-init failed for {api_record.name}: {str(e)}")
            
            _logger.info("[secure_api] Post-init registration completed")
        else:
            _logger.info("[secure_api] Post-init: No published APIs found to register")
            
    except Exception as e:
        _logger.error(f"[secure_api] Post-init error: {str(e)}")
