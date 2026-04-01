{
    "name": "Gainde Partner Legal",
    "summary": "Champs légaux partenaires (forme juridique, RCCM) + validations",
    "version": "18.0.1.0.0",
    "author": "Gainde",
    "license": "LGPL-3",
    "category": "Contacts",
    "depends": [
        "base",
        "purchase",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/form_juridique_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
}
