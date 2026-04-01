{
    "name": "Gainde - Global Sync",
    "version": "18.0.1.0.0",
    "category": "Administration",
    "summary": "Méta-module Gainde (installe les modules de profils par domaine sans dupliquer les profile types).",
    "depends": [
        "audit_gainde",
        "purchase_gainde",
        # "gainde_legal_contract",
        # "gainde_project_management",
	# "helpdesk",
        "asset_management",
        "treasury_management",
    ],
    "data": [
        "data/config/user_profiles_config.xml",
    ],
    "installable": True,
    "application": False,
}
