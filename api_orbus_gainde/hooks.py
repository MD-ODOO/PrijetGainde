from odoo import api, SUPERUSER_ID


def post_init_hook(env_or_cr, registry=None):
    """Ensure Orbus config XMLID exists or create default config.

    This prevents duplicate creation errors on module upgrades when a config
    already exists without its external id.
    """
    # Odoo v18+ calls hooks with a single `env` argument:
    #   getattr(py_module, post_init)(env)
    # Older versions may call with `cr` (and optionally `registry`).
    if isinstance(env_or_cr, api.Environment):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    xmlid = "api_orbus_gainde.orbus_api_config_main_company"
    if env.ref(xmlid, raise_if_not_found=False):
        return

    main_company = env.ref("base.main_company", raise_if_not_found=False)
    if not main_company:
        return

    config = env["orbus.api.config"].search([
        ("company_id", "=", main_company.id),
    ], limit=1)

    if not config:
        config = env["orbus.api.config"].create({
            "company_id": main_company.id,
            "name": "Orbus Préprod",
        })

    env["ir.model.data"].create({
        "module": "api_orbus_gainde",
        "name": "orbus_api_config_main_company",
        "model": "orbus.api.config",
        "res_id": config.id,
        "noupdate": True,
    })
