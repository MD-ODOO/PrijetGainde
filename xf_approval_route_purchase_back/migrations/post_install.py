from odoo import api, SUPERUSER_ID
import logging

_logger = logging.getLogger(__name__)

def post_init_assign_default_route(cr, registry):
    """
    Assign default approval route to existing purchase.requests that don't have approval_route_id
    and whose company use_approval_route_purchase is truthy.
    This function is run once after module install/update if configured in __manifest__.
    """
    env = api.Environment(cr, SUPERUSER_ID, registry)
    PR = env["purchase.request"].search([("approval_route_id", "=", False)])
    if not PR:
        _logger.info("xf_approval_route_purchase: no purchase.request to migrate.")
        return

    default_ref = env.ref(
        "xf_approval_route_purchase.xf_route_purchase_request_default", raise_if_not_found=False
    )
    updated = 0
    for pr in PR:
        company = pr.company_id or env.company
        if getattr(company, "use_approval_route_purchase", False):
            route = default_ref
            if not route or (route.company_id and route.company_id.id != company.id):
                route = env["approval.route"].search(
                    [("model", "=", "purchase.request"), ("company_id", "in", [company.id, False])],
                    limit=1,
                )
            if route:
                pr.write({"approval_route_id": route.id})
                updated += 1

    _logger.info("xf_approval_route_purchase: assigned default approval route to %s purchase.requests", updated)