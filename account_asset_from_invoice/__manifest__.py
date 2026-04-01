{
    "name": "Create Asset from Invoice",
    "version": "18.0.1.2.0",
    "category": "Accounting",
    "summary": "Create fixed assets from vendor bill lines",
    "author": "Moctar Diallo",
    "depends": [
        "account",
        "account_asset",
        "purchase",
    ],
    "data": [
        # "views/account_move_view.xml",
        "views/res_partner_view.xml",
        "views/account_asset_view.xml",

    ],
    "installable": True,
    "application": False,
}
