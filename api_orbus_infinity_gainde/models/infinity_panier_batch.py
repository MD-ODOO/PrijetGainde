import json
import base64
import io
import re
import unicodedata

from odoo import api, fields, models, _
from odoo.tools import html_escape


class OrbusInfinityPanierBatch(models.Model):
    _name = "orbus.infinity.panier.batch"
    _description = "Lot de paniers Orbus Infinity"
    _order = "request_date desc, id desc"

    name = fields.Char(
        string="Libellé",
        required=True,
        default=lambda self: _("Batch paniers Orbus Infinity"),
    )

    code = fields.Char(
        string="Référence batch",
        required=True,
        help="Référence basée sur la date et les paramètres utilisés.",
    )

    params_json = fields.Text(
        string="Paramètres bruts",
        help="Paramètres utilisés pour appeler list-panier.",
    )

    raw_response = fields.Text(
        string="Réponse brute",
        help="Réponse brute list-panier pour diagnostic.",
    )

    status_code = fields.Char(string="Code statut")
    status = fields.Char(string="Statut")
    message = fields.Char(string="Message")

    total_elements = fields.Integer(string="Total éléments")
    total_pages = fields.Integer(string="Total pages")
    page_size = fields.Integer(string="Taille page")
    page_number = fields.Integer(string="Numéro page")

    request_date = fields.Datetime(
        string="Date de récupération",
        default=lambda self: fields.Datetime.now(),
    )

    company_id = fields.Many2one(
        "res.company",
        string="Société",
        required=True,
        default=lambda self: self.env.company,
    )

    line_ids = fields.One2many(
        "orbus.infinity.panier.batch.line",
        "batch_id",
        string="Paniers",
    )

    api_summary_html = fields.Html(
        string="Synthèse API",
        compute="_compute_api_summary_html",
        store=True,
    )

    export_xlsx_file = fields.Binary(
        string="Export Excel",
        readonly=True,
        copy=False,
        attachment=True,
    )
    export_xlsx_filename = fields.Char(
        string="Nom fichier export",
        readonly=True,
        copy=False,
    )
    total_lines = fields.Integer(
        string="Nb. paniers",
        compute="_compute_totals",
        store=True,
    )
    total_montant_ttc = fields.Float(
        string="Total TTC",
        compute="_compute_totals",
        store=True,
    )
    total_montant_ht = fields.Float(
        string="Total HT",
        compute="_compute_totals",
        store=True,
    )
    total_montant_tva = fields.Float(
        string="Total TVA",
        compute="_compute_totals",
        store=True,
    )
    total_paid_ttc = fields.Float(
        string="Total TTC payé",
        compute="_compute_totals",
        store=True,
    )
    total_part_gainde_ttc = fields.Float(
        string="Part GAINDE (33%)",
        compute="_compute_totals",
        store=True,
    )
    total_part_guce_ttc = fields.Float(
        string="Part GUCE (67%)",
        compute="_compute_totals",
        store=True,
    )

    @api.depends(
        "line_ids.montant_ttc",
        "line_ids.montant_ht",
        "line_ids.montant_tva",
        "line_ids.payer",
    )
    def _compute_totals(self):
        for batch in self:
            lines = batch.line_ids
            batch.total_lines = len(lines)
            batch.total_montant_ttc = sum(lines.mapped("montant_ttc"))
            batch.total_montant_ht = sum(lines.mapped("montant_ht"))
            batch.total_montant_tva = sum(lines.mapped("montant_tva"))
            paid_lines = lines.filtered("payer")
            batch.total_paid_ttc = sum(paid_lines.mapped("montant_ttc"))
            batch.total_part_gainde_ttc = (batch.total_montant_ttc or 0.0) * 0.33
            batch.total_part_guce_ttc = (batch.total_montant_ttc or 0.0) * 0.67

    def _build_summary_html(self, errors, result_text):
        if errors:
            items = "".join(
                "<li><strong>%s</strong> : %s</li>" % (
                    html_escape(label),
                    html_escape(msg),
                )
                for label, msg in errors
            )
            return (
                "<div>"
                "<span class='badge badge-danger'>Erreurs</span>"
                "<ul>"
                + items
                + "</ul>"
                "</div>"
            )

        result_text = result_text or "Aucune erreur détectée."
        return (
            "<div>"
            "<span class='badge badge-success'>OK</span>"
            "<div>"
            + html_escape(result_text)
            + "</div>"
            "</div>"
        )

    @api.depends(
        "line_ids.state",
        "line_ids.error_message",
        "line_ids.reference_panier",
        "line_ids.numero_dossier",
        "message",
        "status",
        "status_code",
    )
    def _compute_api_summary_html(self):
        for batch in self:
            errors = []
            for line in batch.line_ids:
                if line.state == "error":
                    label = line.reference_panier or line.numero_dossier or "Ligne %s" % line.id
                    msg = line.error_message or "Erreur inconnue"
                    errors.append((label, msg))

            result_parts = []
            if batch.message:
                result_parts.append(batch.message)
            if batch.status_code:
                result_parts.append("Code %s" % batch.status_code)
            if batch.status:
                result_parts.append(batch.status)

            result_text = " - ".join(result_parts)
            batch.api_summary_html = batch._build_summary_html(errors, result_text)

    def action_create_invoices(self):
        """Crée en masse les factures Odoo pour les lignes non facturées."""
        for batch in self:
            config = self.env["orbus.infinity.api.config"].get_config_for_company(batch.company_id)
            pending_lines = batch.line_ids.filtered(lambda l: not l.invoice_id)
            for line in pending_lines:
                try:
                    invoice = config.create_odoo_invoice_from_panier_line(line)
                except Exception as e:  # pragma: no cover
                    line.state = "error"
                    line.error_message = str(e)
                    continue

                line.invoice_id = invoice.id
                line.state = "invoiced"
                line.error_message = False

            # Enregistrer automatiquement les paiements pour les lignes payées.
            batch.action_register_payments()

    def action_register_payments(self):
        """Enregistre les paiements Odoo pour les factures liées aux lignes payées.

        - Ne traite que les lignes `payer=True`.
        - Si une facture existe déjà et n'est pas payée, on utilise le même
          mécanisme que lors de la création de facture (payment.register).
        - Met aussi à jour les références Infinity sur la facture.
        """
        for batch in self:
            config = self.env["orbus.infinity.api.config"].get_config_for_company(batch.company_id)
            for line in batch.line_ids.filtered(lambda l: l.payer and l.invoice_id):
                try:
                    line._orbus_infinity_sync_invoice_references()
                    invoice = line.invoice_id

                    # Déjà payé ou rien à payer
                    if getattr(invoice, "payment_state", False) == "paid":
                        continue
                    if invoice.amount_residual <= 0:
                        continue

                    config._register_payment_for_invoice(
                        invoice,
                        source=line.source,
                        payment_date=line.date_paiement,
                        payment_reference=line.numero_paiement or line.reference_panier,
                    )
                except Exception as e:  # pragma: no cover
                    line.state = "error"
                    line.error_message = str(e)
                    continue

        return True

    def action_export_xlsx(self):
        """Exporte les données traitées (lignes) + un récap TTC/HT/TVA en XLSX.

        Feuille 1: Données traitées (une ligne par panier).
        Feuille 2: Récapitulatif (Total + Payé) TTC/HT/TVA.
        """
        self.ensure_one()

        # Import local pour éviter une dépendance à l'analyse statique hors conteneur.
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        fmt_header = workbook.add_format({"bold": True, "bg_color": "#E6E6E6"})
        fmt_money = workbook.add_format({"num_format": "#,##0.00"})
        fmt_date = workbook.add_format({"num_format": "yyyy-mm-dd hh:mm"})

        # Sheet 1: données
        sheet1 = workbook.add_worksheet("Donnees")
        headers = [
            "Référence panier",
            "Numéro dossier",
            "Numéro paiement",
            "Source paiement",
            "Date paiement",
            "Date génération référence",
            "Payé",
            "Collectionneur",
            "Transitaire",
            "Connaissement",
            "Destination",
            "Zone",
            "Montant TTC",
            "Part GAINDE (33%)",
            "Part GUCE (67%)",
            "Montant HT",
            "Montant TVA",
            "Nb factures",
            "État",
            "Facture Odoo",
        ]
        for col, label in enumerate(headers):
            sheet1.write(0, col, label, fmt_header)

        row = 1
        for line in self.line_ids:
            invoice_name = line.invoice_id.name if line.invoice_id else ""

            date_paiement = line.date_paiement
            if isinstance(date_paiement, str):
                date_paiement = fields.Datetime.to_datetime(date_paiement)
            date_gen = line.date_generate_reference
            if isinstance(date_gen, str):
                date_gen = fields.Datetime.to_datetime(date_gen)

            values = [
                line.reference_panier or "",
                line.numero_dossier or "",
                line.numero_paiement or "",
                line.source or "",
                date_paiement,
                date_gen,
                bool(line.payer),
                bool(line.collectionneur),
                line.transitaire or "",
                line.connaissement or "",
                line.destination_pays or "",
                ("National" if line.zone == "national" else "International"),
                line.montant_ttc or 0.0,
                line.part_gainde_ttc or 0.0,
                line.part_guce_ttc or 0.0,
                line.montant_ht or 0.0,
                line.montant_tva or 0.0,
                line.factures_count or 0,
                line.state or "",
                invoice_name,
            ]

            for col, val in enumerate(values):
                if col in (4, 5):
                    if val:
                        sheet1.write_datetime(row, col, val, fmt_date)
                    else:
                        sheet1.write(row, col, "")
                elif col in (12, 13, 14, 15, 16):
                    sheet1.write_number(row, col, float(val or 0.0), fmt_money)
                elif col == 17:
                    sheet1.write_number(row, col, int(val or 0))
                elif col in (6, 7):
                    sheet1.write(row, col, "Oui" if val else "Non")
                else:
                    sheet1.write(row, col, val)

            row += 1

        sheet1.freeze_panes(1, 0)
        sheet1.autofilter(0, 0, max(row - 1, 0), len(headers) - 1)

        # Sheet 2: récap
        sheet2 = workbook.add_worksheet("Recap")
        sheet2.write(0, 0, "Indicateur", fmt_header)
        sheet2.write(0, 1, "TTC", fmt_header)
        sheet2.write(0, 2, "HT", fmt_header)
        sheet2.write(0, 3, "TVA", fmt_header)
        sheet2.write(0, 4, "Part GAINDE (33%)", fmt_header)
        sheet2.write(0, 5, "Part GUCE (67%)", fmt_header)

        all_lines = self.line_ids
        paid_lines = all_lines.filtered("payer")
        total_ttc = sum(all_lines.mapped("montant_ttc"))
        total_ht = sum(all_lines.mapped("montant_ht"))
        total_tva = sum(all_lines.mapped("montant_tva"))
        total_part_gainde = sum(all_lines.mapped("part_gainde_ttc"))
        total_part_guce = sum(all_lines.mapped("part_guce_ttc"))
        paid_ttc = sum(paid_lines.mapped("montant_ttc"))
        paid_ht = sum(paid_lines.mapped("montant_ht"))
        paid_tva = sum(paid_lines.mapped("montant_tva"))
        paid_part_gainde = sum(paid_lines.mapped("part_gainde_ttc"))
        paid_part_guce = sum(paid_lines.mapped("part_guce_ttc"))

        sheet2.write(1, 0, "Total")
        sheet2.write_number(1, 1, float(total_ttc or 0.0), fmt_money)
        sheet2.write_number(1, 2, float(total_ht or 0.0), fmt_money)
        sheet2.write_number(1, 3, float(total_tva or 0.0), fmt_money)
        sheet2.write_number(1, 4, float(total_part_gainde or 0.0), fmt_money)
        sheet2.write_number(1, 5, float(total_part_guce or 0.0), fmt_money)

        grouped = {}
        for line in all_lines:
            key = line.payment_journal_label or "Non identifié"
            grouped.setdefault(
                key,
                {
                    "ttc": 0.0,
                    "ht": 0.0,
                    "tva": 0.0,
                    "gainde": 0.0,
                    "guce": 0.0,
                },
            )
            grouped[key]["ttc"] += line.montant_ttc or 0.0
            grouped[key]["ht"] += line.montant_ht or 0.0
            grouped[key]["tva"] += line.montant_tva or 0.0
            grouped[key]["gainde"] += line.part_gainde_ttc or 0.0
            grouped[key]["guce"] += line.part_guce_ttc or 0.0

        row = 2
        for source in sorted(grouped.keys(), key=lambda s: s.lower()):
            totals = grouped[source]
            sheet2.write(row, 0, source)
            sheet2.write_number(row, 1, float(totals["ttc"] or 0.0), fmt_money)
            sheet2.write_number(row, 2, float(totals["ht"] or 0.0), fmt_money)
            sheet2.write_number(row, 3, float(totals["tva"] or 0.0), fmt_money)
            sheet2.write_number(row, 4, float(totals["gainde"] or 0.0), fmt_money)
            sheet2.write_number(row, 5, float(totals["guce"] or 0.0), fmt_money)
            row += 1

        workbook.close()
        output.seek(0)

        filename = f"orbus_infinity_batch_{(self.code or self.id)}.xlsx"
        self.write(
            {
                "export_xlsx_file": base64.b64encode(output.read()),
                "export_xlsx_filename": filename,
            }
        )

        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/?model=orbus.infinity.panier.batch"
                f"&id={self.id}"
                "&field=export_xlsx_file"
                "&filename_field=export_xlsx_filename"
                "&download=true"
            ),
            "target": "self",
        }

    def action_delete_lines(self):
        """Supprime toutes les lignes du batch."""
        for batch in self:
            batch.line_ids.unlink()
        return True


class OrbusInfinityPanierBatchLine(models.Model):
    _name = "orbus.infinity.panier.batch.line"
    _description = "Panier Orbus Infinity dans un lot"
    _order = "id desc"

    batch_id = fields.Many2one(
        "orbus.infinity.panier.batch",
        string="Lot",
        required=True,
        ondelete="cascade",
    )

    reference_panier = fields.Char(string="Référence panier")
    numero_dossier = fields.Char(string="Numéro dossier")
    numero_paiement = fields.Char(string="Numéro paiement")
    source = fields.Char(
        string="Source / moyen de paiement",
        help="Moyen de paiement renvoyé par Infinity (ex: ICRS, ON DEPOSIT, ORBUS PAIEMENT).",
    )
    payment_journal_label = fields.Char(
        string="Journal de paiement",
        compute="_compute_payment_journal_label",
        store=True,
    )

    date_paiement = fields.Datetime(string="Date paiement")
    date_generate_reference = fields.Datetime(string="Date génération référence")

    payer = fields.Boolean(string="Payé")
    collectionneur = fields.Boolean(string="Collectionneur")
    transitaire = fields.Char(string="Transitaire")
    connaissement = fields.Char(string="Connaissement")

    # IMPORTANT: ne pas changer le type historique (Selection) -> sinon l'upgrade
    # peut échouer lors du nettoyage des ir.model.fields.selection.
    destination = fields.Selection(
        selection=[
            ("IMPORT", "Import"),
            ("EXPORT", "Export"),
            ("TRANSIT", "Transit"),
        ],
        string="Destination (legacy)",
    )

    destination_pays = fields.Char(string="Destination (Pays)")

    zone = fields.Selection(
        selection=[
            ("national", "National"),
            ("international", "International"),
        ],
        string="Zone",
        compute="_compute_zone",
        store=True,
    )

    montant_ttc = fields.Float(string="Montant TTC")
    montant_ht = fields.Float(string="Montant HT")
    montant_tva = fields.Float(string="Montant TVA")

    part_gainde_ttc = fields.Float(
        string="Part GAINDE (33%)",
        compute="_compute_parts",
        store=True,
    )
    part_guce_ttc = fields.Float(
        string="Part GUCE (67%)",
        compute="_compute_parts",
        store=True,
    )

    factures_json = fields.Text(
        string="Factures (JSON)",
        help="Factures détaillées renvoyées par l'API list-panier.",
    )

    factures_count = fields.Integer(string="Nombre de factures")

    invoice_id = fields.Many2one(
        "account.move",
        string="Facture Odoo",
        readonly=True,
    )

    state = fields.Selection(
        [
            ("pending", "En attente"),
            ("invoiced", "Facture créée"),
            ("error", "Erreur"),
        ],
        string="État facture",
        default="pending",
        readonly=False,
    )

    error_message = fields.Char(string="Message d'erreur")

    company_id = fields.Many2one(
        related="batch_id.company_id",
        store=True,
        readonly=True,
    )

    @api.depends("montant_ttc")
    def _compute_parts(self):
        for line in self:
            montant = line.montant_ttc or 0.0
            line.part_gainde_ttc = montant * 0.33
            line.part_guce_ttc = montant * 0.67

    @api.depends("destination_pays")
    def _compute_zone(self):
        def _norm(value: str) -> str:
            value = (value or "").strip()
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
            value = value.lower()
            return " ".join(value.split())

        def _is_senegal(value_norm: str) -> bool:
            if not value_norm:
                return False
            cleaned = re.sub(r"[^a-z0-9]+", " ", value_norm)
            tokens = {t for t in cleaned.split() if t}
            if tokens == {"sn"}:
                return True
            if "senegal" in tokens:
                return True
            if {"republique", "du", "senegal"}.issubset(tokens):
                return True
            return False

        for line in self:
            dest_norm = _norm(line.destination_pays or "")
            line.zone = "national" if _is_senegal(dest_norm) else "international"

    @api.depends("source")
    def _compute_payment_journal_label(self):
        def _norm(value: str) -> str:
            value = (value or "").strip()
            value = unicodedata.normalize("NFKD", value)
            value = "".join(ch for ch in value if not unicodedata.combining(ch))
            value = value.lower()
            return " ".join(value.split())

        for line in self:
            norm = _norm(line.source)
            if "icrs" in norm or "espece" in norm or "espèce" in norm or "cash" in norm:
                line.payment_journal_label = "ICRS"
            elif "virement" in norm or "transfer" in norm or "bank" in norm:
                line.payment_journal_label = "ICRS"
            elif "cheque" in norm or "chèque" in norm or "check" in norm:
                line.payment_journal_label = "ICRS"
            elif "deposit" in norm or "depot" in norm or "wallet" in norm or "on deposit" in norm:
                line.payment_journal_label = "ON DEPOSIT"
            elif "orange" in norm or "mobile" in norm or "wave" in norm or "carte" in norm or "card" in norm:
                line.payment_journal_label = "OBRUS PAYMENT"
            elif "orbus" in norm and ("pai" in norm or "payment" in norm):
                line.payment_journal_label = "OBRUS PAYMENT"
            else:
                line.payment_journal_label = "Non identifié"

    def get_factures(self):
        self.ensure_one()
        if not self.factures_json:
            return []
        try:
            return json.loads(self.factures_json) or []
        except Exception:  # pragma: no cover
            return []

    def _orbus_infinity_sync_invoice_references(self):
        """Synchronise les références Infinity sur la facture liée (si présente)."""
        for line in self.filtered("invoice_id"):
            invoice = line.invoice_id
            vals = {
                "orbus_infinity_reference_panier": line.reference_panier,
                "orbus_infinity_numero_dossier": line.numero_dossier,
                "orbus_infinity_numero_paiement": line.numero_paiement,
                "orbus_infinity_source": line.source,
                "orbus_infinity_date_paiement": line.date_paiement,
                "orbus_infinity_date_generate_reference": line.date_generate_reference,
                "orbus_infinity_transitaire": line.transitaire,
                "orbus_infinity_connaissement": line.connaissement,
                "orbus_infinity_destination": False,
                "orbus_infinity_destination_pays": line.destination_pays,
                "orbus_infinity_payer": line.payer,
                "orbus_infinity_factures_json": line.factures_json,
                "orbus_infinity_montant_facture": line.montant_ttc,
                "orbus_infinity_batch_line_id": line.id,
            }
            invoice.sudo().write(vals)

        return True
