import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def pre_init_hook(env_or_cr):
        """Avant upgrade/installation: nettoyer les sélections orphelines.

        Quand un champ a été un `selection` puis devient un `char`, Odoo peut planter
        lors du nettoyage des `ir.model.fields.selection` (car un Char n'a pas
        d'attribut `ondelete`).

        On supprime donc les lignes de sélection historiques associées à ces champs.
        """

        cr = env_or_cr.cr if isinstance(env_or_cr, api.Environment) else env_or_cr

        # account.move.orbus_infinity_destination : était un selection (IMPORT/EXPORT/TRANSIT)
        # puis est devenu un Char (pays). On purge ses valeurs de sélection.
        cr.execute(
                """
                DELETE FROM ir_model_fields_selection s
                USING ir_model_fields f
                JOIN ir_model m ON m.id = f.model_id
                WHERE s.field_id = f.id
                    AND m.model = %s
                    AND f.name = %s
                    AND f.ttype <> 'selection'
                """,
                ("account.move", "orbus_infinity_destination"),
        )

        return True


def _find_free_account_code(env, company, start_code: int) -> str:
    Account = env["account.account"].sudo().with_company(company)
    code = int(start_code)
    while Account.search_count([("company_id", "=", company.id), ("code", "=", str(code))]):
        code += 1
    return str(code)


def _ensure_account(env, company, *, name: str, start_code: int, account_type: str):
    Account = env["account.account"].sudo().with_company(company)

    # 1) Déjà existant par nom
    account = Account.search([("company_id", "=", company.id), ("name", "=", name)], limit=1)
    if account:
        return account

    # 2) Créer avec un code libre
    code = _find_free_account_code(env, company, start_code)
    vals = {
        "name": name,
        "code": code,
        "company_id": company.id,
    }

    # Odoo récent (v18): account_type est un champ natif
    if "account_type" in Account._fields:
        vals["account_type"] = account_type

    return Account.create(vals)


def _ensure_journal(env, company, *, name: str, code: str, default_account, journal_type="bank"):
    Journal = env["account.journal"].sudo().with_company(company)

    journal = Journal.search(
        [
            ("company_id", "=", company.id),
            ("code", "=", code),
        ],
        limit=1,
    )
    if journal:
        # S'assurer que le compte de liquidité est bien renseigné
        if default_account and getattr(journal, "default_account_id", False) != default_account:
            journal.write({"default_account_id": default_account.id})
        return journal

    # Fallback par nom
    journal = Journal.search([("company_id", "=", company.id), ("name", "=", name)], limit=1)
    if journal:
        if default_account and getattr(journal, "default_account_id", False) != default_account:
            journal.write({"default_account_id": default_account.id})
        return journal

    vals = {
        "name": name,
        "code": code,
        "type": journal_type,
        "company_id": company.id,
    }
    if default_account and "default_account_id" in Journal._fields:
        vals["default_account_id"] = default_account.id

    return Journal.create(vals)


def _ensure_inbound_payment_method_line(env, journal, *, label: str):
    """S'assure qu'un moyen de paiement entrant existe sur le journal."""
    journal = journal.sudo()
    if "inbound_payment_method_line_ids" not in journal._fields:
        return False

    if journal.inbound_payment_method_line_ids.filtered(lambda l: l.name == label):
        return True

    PaymentMethod = env["account.payment.method"].sudo()
    method = PaymentMethod.search(
        [
            ("payment_type", "=", "inbound"),
            ("code", "=", "manual"),
        ],
        limit=1,
    )
    if not method:
        method = PaymentMethod.search([
            ("payment_type", "=", "inbound"),
        ], limit=1)

    if not method:
        return False

    env["account.payment.method.line"].sudo().create(
        {
            "name": label,
            "journal_id": journal.id,
            "payment_method_id": method.id,
        }
    )
    return True


def post_init_hook(env_or_cr, registry=None):
    """À l'installation: créer les comptes/journaux de paiement si absents.

    Comptes demandés:
    - ICRS (ESPECES / VIREMENT / CHEQUE)
    - OBRUS PAYMENT (PAIEMENT EN LIGNE)
    - ORBUS INFINITY (fallback technique)

    Note: on crée des comptes de type liquidité (asset_cash) pour permettre
    l'enregistrement des paiements via un journal banque/caisse.
    """
    # Odoo v18+ calls hooks with a single `env` argument.
    if isinstance(env_or_cr, api.Environment):
        env = env_or_cr
    else:
        env = api.Environment(env_or_cr, SUPERUSER_ID, {})

    companies = env["res.company"].sudo().search([])
    for company in companies:
        try:
            # Codes indicatifs: 512900+ (banque/caisse). On prend le prochain code libre.
            acc_infinity = _ensure_account(
                env,
                company,
                name="ORBUS INFINITY (PLATEFORME EXTERNE)",
                start_code=512900,
                account_type="asset_cash",
            )
            acc_icrs = _ensure_account(
                env,
                company,
                name="ICRS (PLATEFORME EXTERNE)",
                start_code=512910,
                account_type="asset_cash",
            )
            # Compat: certains environnements l'ont déjà sous un libellé plus court.
            Account = env["account.account"].sudo().with_company(company)
            acc_deposit = Account.search(
                [
                    ("company_id", "=", company.id),
                    ("name", "in", [
                        "ON DEPOSIT (COMPTE DEPOSIT DU CLIENT ABONNÉS OU COLLECTIONNEUR)",
                        "ON DEPOSIT (COMPTE DEPOSIT CLIENT)",
                    ]),
                ],
                limit=1,
            )
            if not acc_deposit:
                acc_deposit = _ensure_account(
                    env,
                    company,
                    name="ON DEPOSIT (COMPTE DEPOSIT DU CLIENT ABONNÉS OU COLLECTIONNEUR)",
                    start_code=512920,
                    account_type="asset_cash",
                )
            acc_orbus_pay = _ensure_account(
                env,
                company,
                name="ORBUS PAYMENT (PLATEFORME DE PAIEMENT)",
                start_code=512930,
                account_type="asset_cash",
            )

            journal_infinity = _ensure_journal(env, company, name="ORBUS INFINITY", code="OINF", default_account=acc_infinity)
            journal_icrs = _ensure_journal(
                env,
                company,
                name="ICRS",
                code="ICRS",
                default_account=acc_icrs,
                journal_type="cash",
            )
            journal_deposit = _ensure_journal(env, company, name="ON DEPOSIT", code="DEP", default_account=acc_deposit)
            journal_orbus = _ensure_journal(
                env,
                company,
                name="OBRUS PAYMENT",
                code="ORBP",
                default_account=acc_orbus_pay,
                journal_type="bank",
            )

            _ensure_inbound_payment_method_line(env, journal_infinity, label="ORBUS INFINITY")
            _ensure_inbound_payment_method_line(env, journal_icrs, label="ICRS")
            _ensure_inbound_payment_method_line(env, journal_deposit, label="ON_DEPOSIT")
            _ensure_inbound_payment_method_line(env, journal_orbus, label="OBRUS PAYMENT")
        except Exception as e:  # pragma: no cover
            _logger.exception("[OrbusInfinity][post_init_hook] Erreur création comptes/journaux (company=%s): %s", company.display_name, e)
            continue

    # Cron global (une seule fois): batch collectionneur tous les 15 jours
    try:
        Cron = env["ir.cron"].sudo()
        model = env["ir.model"].sudo()._get("orbus.infinity.api.config")
        if model:
            root_user = (
                env.ref("base.user_root", raise_if_not_found=False)
                or env.ref("base.user_admin", raise_if_not_found=False)
            )
            user_id = root_user.id if root_user else 1

            name = "Orbus Infinity: batch collectionneur (15 jours)"
            code = "model.cron_fetch_collectionneur_batches()"
            cron = Cron.search(
                [
                    ("model_id", "=", model.id),
                    ("state", "=", "code"),
                    ("code", "=", code),
                ],
                limit=1,
            )
            vals = {
                "name": name,
                "active": True,
                "user_id": user_id,
                "interval_number": 15,
                "interval_type": "days",
                "numbercall": -1,
                "doall": False,
                "model_id": model.id,
                "state": "code",
                "code": code,
            }
            if cron:
                cron.write(vals)
            else:
                Cron.create(vals)
    except Exception as e:  # pragma: no cover
        _logger.exception("[OrbusInfinity][post_init_hook] Erreur création cron: %s", e)

    return True
