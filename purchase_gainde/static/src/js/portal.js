/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { renderToElement } from "@web/core/utils/render";
import { parseDate, serializeDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.portalPurchaseRequest = publicWidget.Widget.extend({
    selector: '.o_purchase_request_portal_sidebar',
    events: {
        'click .edit_confirm': '_onEditConfirm',
        'click button[name="o_add_line_button"]': '_onClickRequestLineAdd',
        'click .o_purchase_line_js_delete': '_onClickRequestLineDelete',
        'click .o_purchase_js_delete': '_onClickRequestDelete',
        'click .o_purchase_js_approve': '_onClickRequestApprove',
        'change select[name="company_id"]': '_onCompanyChange',
    },
    Lines: [],
    _validateInputs: function (rows) {
        var hasErrors = false;
        $('.js_select2_picking_type_id').css('border', '');
        if (!$('.js_select2_picking_type_id').val()) {
            $('.js_select2_picking_type_id').css('border', '1px solid red');
            hasErrors = false;
        }
        rows.each((i, row) => {
            let product_id = $(row).find('.o_input_product').data('product-id');
            let name = $(row).find('.o_input_portal_product_description').val();
            let qty = $(row).find('.o_input_quantity').val();

            // Nettoyer toute bordure rouge appliquée précédemment
            $(row).find('.o_input_portal_product_description').css('border', '');
            $(row).find('.o_input_quantity').css('border', '');

            // Vérifier que le produit est sélectionné
            if (!product_id) {
                $(row).find('.o_input_product').css('border', '1px solid red');
                hasErrors = true;
            }

            // Vérifier que la quantité n'est pas vide et est strictement positive
            if (!qty || qty <= 0) {
                $(row).find('.o_input_quantity').css('border', '1px solid red');
                hasErrors = true;
            }
        });

        return !hasErrors;
    },
    _onEditConfirm: function (doReload = true) {
        var rows = $('.items > tbody > tr.o_data_row');

        // Vérifier que les champs obligatoires ne sont pas vides
        if (!this._validateInputs(rows)) {
            return false; // Empêche l'envoi du formulaire en cas d'erreurs
        }

        rows.each((i, row) => {
            let product_id = $(row).find('.o_input_product').data('product-id');
            let name = $(row).find('.o_input_portal_product_description').val();
            let qty = $(row).find('.o_input_quantity').val();
            let uom_id = $(row).find('.o_input_uom').data('uom-id');
            let data_id = $(row).data('id'); // Récupérer l'attribut data-id

            // S'il n'a pas de data-id, c'est une nouvelle ligne
            if (!data_id) {
                this.Lines.push([0, 0, {
                    'product_id': product_id,
                    'name': name,
                    'portal_product_description': name,
                    'product_qty': qty,
                    'product_uom_id': uom_id,
                }]);
            } else {
                // En cas de mise à jour, il n'est plus nécessaire de modifier le name
                this.Lines.push([1, data_id, {
                    'id': data_id,
                    'product_id': product_id,
                    'portal_product_description': name,
                    'product_qty': qty,
                    'product_uom_id': uom_id,
                }]);
            }
        });

        // Enregistrer les lignes dans le textarea (si tout est correct)
        $("textarea[name='line_ids']").val(JSON.stringify(this.Lines));

        // Mettre à jour le champ date_start au format UTC
        $('.edit_form .date_start').val(this._parse_date($('.edit_form .date_start').val()));

        // Continuer le flux normal s'il n'y a pas d'erreurs
        return true;
    },
    _validateAddProductLine: function (data) {
        var isValid = false;
        // Nettoyer les styles de validation appliqués précédemment
        $('.product_js_select2, .portal_description, .uom_js_select2').css('border', '');

        const hasProduct = Array.isArray(data.product) ? data.product.length > 0 : !!data.product;

        if (!hasProduct) {
            $('.product_js_select2').css('border', '1px solid red');
            isValid = true;
        }

        if (hasProduct && !data.uom) {
            $('.uom_js_select2').css('border', '1px solid red');
            isValid = true;
        }

        return !isValid;
    },
    _onClickRequestLineAdd: function (doReload = true) {
        var $form = this.$('.edit_form');

        var $productSelect = $form.find('.product_js_select2');
        var $uomSelect = $form.find('.uom_js_select2');
        var $qtyInput = $form.find('.qty');
        var $portalDescription = $form.find('.portal_description');

        var product = $productSelect.select2('data');
        var uom = $uomSelect.select2('data');
        var qty = $qtyInput.val();
        var portal_description = $portalDescription.val();

        var data = {
            product: product,
            uom: uom,
            product_qty: qty,
            portal_product_description: portal_description
        };

        if (!this._validateAddProductLine(data)) {
            return false;
        }

        var tmpl_line = renderToElement(
            'bf_portal_purchase_request.purchase_request_line',
            data
        );

        var tbody = this.$('.table-body')[0];
        tbody.appendChild(tmpl_line);

        // Update table visibility
        this._actualizarVisibilidadTabla();

        /* ============================
           RESET INPUTS AFTER ADD
           ============================ */

        // Clear Select2 fields
        $productSelect
            .val(null)
            .trigger('change')
            .trigger('change.select2');

        // 🔒 FORCE reset UoM Select2
        $uomSelect
            .val(null)
            .trigger('change')
            .trigger('change.select2');
        $productSelect.select2('data', null);
        $uomSelect.select2('data', null);


        // Reset quantity (integer, not decimal)
        $qtyInput.val(1);

        // Clear description
        $portalDescription.val('');

        // Focus back to product for fast entry
        //$productSelect.select2('open');

        return true;
    },

    /**
     * @private
     * @param {Event} ev
     */
    _onClickRequestLineDelete: function (ev) {
        ev.preventDefault();
        var $row = $(ev.currentTarget).closest('tr');
        var data_id = $row.data('id'); // Obtener el id de la fila eliminada

        // Si la fila tiene data-id, añadirla a Lines
        if (data_id) {
            this.Lines.push([2, data_id, false]);
        }
        // Remover la fila del DOM
        $row.remove();
        this._actualizarVisibilidadTabla();
    },
    /**
     * @override
     */
    start: function () {
        $('.js_select2_assigned_to').select2({ allowClear: true });
        $('.product_js_select2').select2({
            allowClear: true,
            ajax: {
                url: '/purchase_request/products',
                dataType: 'json',
                data: function (term) {
                    return {
                        query: term,
                        limit: 20,
                    };
                },
                results: function (data) {
                    var ret = [];
                    data.forEach((x) => {
                        ret.push({
                            id: x.id,
                            text: x.display_name,
                            uom_id: x.uom_id[0],
                            uom_name: x.uom_id[1],
                        });
                    });
                    self.lastsearch = ret;
                    return { results: ret };
                }
            }
        }).on("select2-selecting", function (e) {
            $('.portal_description').val(e.choice.text);
            $(".uom_js_select2").select2("data", { id: e.choice.uom_id, text: e.choice.uom_name });
        }).on("select2-removed", function (e) {
            $('.portal_description').val('');
        });
        $('.uom_js_select2').select2({
            allowClear: true,
            ajax: {
                url: '/purchase_request/uoms',
                dataType: 'json',
                data: function (term) {
                    return {
                        query: term,
                        limit: 20,
                        uom_id: $('.product_js_select2').select2('data')?.uom_id || undefined,
                    };
                },
                results: function (data) {
                    var ret = [];
                    data.forEach((x) => {
                        ret.push({
                            id: x.id,
                            text: x.display_name,
                        });
                    });
                    self.lastsearch = ret;
                    return { results: ret };
                }
            }
        });
        this._actualizarVisibilidadTabla();
        var def = this._super.apply(this, arguments);

        this.$pickingType = this.$('select[name="picking_type_id"]');
        this.$pickingTypeOptions = this.$pickingType.filter(':enabled').find('option:not(:first)');
        this._adaptStockRequestForm();

        // Afficher un popup d'erreur si le backend a signalé l'absence de lignes
        try {
            const url = new URL(window.location.href);
            const params = url.searchParams;
            if (params.get('no_lines') === '1') {
                this.call("dialog", "add", ConfirmationDialog, {
                    title: _t("Erreur"),
                    body: _t("La demande d'achat doit contenir au moins une ligne."),
                    confirmLabel: _t("OK"),
                    confirm: () => { },
                });

                // Nettoyer l'URL pour éviter de ré-afficher le popup au rafraîchissement
                params.delete('no_lines');
                const newUrl = url.pathname + (params.toString() ? '?' + params.toString() : '') + url.hash;
                window.history.replaceState({}, '', newUrl);
            }
        } catch (e) {
            // En cas de problème avec URL, on ne bloque pas le reste du démarrage
        }

        return def;
    },
    _adaptStockRequestForm: function () {
        var $company = this.$('select[name="company_id"]');
        var companyID = ($company.val() || 0);
        this.$pickingTypeOptions.detach();
        var $displayedStockPicking = this.$pickingTypeOptions.filter('[data-company_id=' + companyID + ']');
        var nb = $displayedStockPicking.appendTo(this.$pickingType).show().length;
        // this.$pickingType.parent().toggle(nb >= 1);
    },
    _onCompanyChange: function () {
        this._adaptStockRequestForm();
    },

    _actualizarVisibilidadTabla: function () {
        var table = this.$('.table-body');
        var rows = table.find('tr');
        if (rows.length > 0) {
            this.$('#js_product_container').show();
        } else {
            this.$('#js_product_container').hide();
        }
    },

    // Ref. website_crm_partner_assign/static/src/js/crm_partner_assign.js
    _parse_date: function (value) {
        var date = parseDate(value);
        if (!date.isValid || date.year < 1900) {
            return false;
        }
        return serializeDate(date);
    },
    async _onClickRequestDelete(ev) {
        ev.preventDefault();
        const confirmed = await new Promise((resolve) =>
            this.call("dialog", "add", ConfirmationDialog, {
                confirm: () => resolve(true),
                title: _t("Supprimer la demande."),
                body: _t("Êtes-vous sûr de vouloir supprimer la demande ?"),
                confirmLabel: _t("Oui"),
                cancel: () => { }, // show cancel button
            })
        );
        if (confirmed) {
            window.location.href = ev.currentTarget.getAttribute('href');
        }
    },
    async _onClickRequestApprove(ev) {
        ev.preventDefault();
        const confirmed = await new Promise((resolve) =>
            this.call("dialog", "add", ConfirmationDialog, {
                confirm: () => resolve(true),
                title: _t("Demande d'approbation."),
                body: _t("Êtes-vous sûr de vouloir soumettre la demande ?"),
                confirmLabel: _t("Oui"),
                cancel: () => { }, // show cancel button
            })
        );
        if (confirmed) {
            window.location.href = ev.currentTarget.getAttribute('href');
        }
    },
});

// Widget global: affiche le popup no_lines sur toutes les pages portail,
// même si la sidebar PR n'est pas présente.
publicWidget.registry.portalPurchaseRequestNoLinesPopup = publicWidget.Widget.extend({
    selector: 'body',
    start: function () {
        const def = this._super.apply(this, arguments);
        try {
            const url = new URL(window.location.href);
            const params = url.searchParams;
            if (params.get('no_lines') === '1') {
                this.call("dialog", "add", ConfirmationDialog, {
                    title: _t("Erreur"),
                    body: _t("La demande d'achat doit contenir au moins une ligne."),
                    confirmLabel: _t("OK"),
                    confirm: () => { },
                });

                // Nettoyer l'URL pour éviter de ré-afficher le popup au rafraîchissement
                params.delete('no_lines');
                const newUrl = url.pathname + (params.toString() ? '?' + params.toString() : '') + url.hash;
                window.history.replaceState({}, '', newUrl);
            }
        } catch (e) {
            // Ne pas bloquer le reste
        }
        return def;
    },
});