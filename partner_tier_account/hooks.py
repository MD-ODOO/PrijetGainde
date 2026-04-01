from odoo import api, SUPERUSER_ID


def post_init_hook(env_or_cr):
    # Odoo v18+ calls hooks with a single `env` argument.
    if isinstance(env_or_cr, api.Environment):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    seq = env.ref("partner_tier_account.seq_account_move_entry_sequence", raise_if_not_found=False)
    if not seq:
        return

    seq.sudo().write({
        "prefix": "",
        "suffix": " - %(year)s",
        "padding": 6,
    })
