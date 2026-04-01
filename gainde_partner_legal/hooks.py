def pre_init_hook(cr_or_env):
    """Evite les doublons lors d'une migration/upgrade.

    Si une base a déjà `purchase_gainde` installé (ancien emplacement des XMLID),
    on déplace les XMLID vers `gainde_partner_legal` avant l'installation/upgrade
    pour que les données (views/menu/action/ACL) soient mises à jour au lieu
    d'être recréées.

    Sur une base neuve, cette opération est un no-op.
    """
    # Odoo peut appeler un pre_init_hook avec un curseur (cr) ou un Environment (env)
    cr = cr_or_env
    if not hasattr(cr, "execute") and hasattr(cr_or_env, "cr"):
        cr = cr_or_env.cr

    xmlids = (
        "view_form_juridique_list",
        "view_form_juridique_form",
        "action_form_juridique",
        "menu_form_juridique",
        "view_partner_form_gainde_rccm",
        "access_form_juridique_manager",
    )

    cr.execute(
        """
        UPDATE ir_model_data
           SET module = %s
         WHERE module = %s
           AND name = ANY(%s)
        """,
        ("gainde_partner_legal", "purchase_gainde", list(xmlids)),
    )
