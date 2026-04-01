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
            hasErrors = true;
        }
        rows.each((i, row) => {
            let name = $(row).find('.o_input_portal_product_description').val();
            let qty = $(row).find('.o_input_quantity').val();

            // Limpiar cualquier borde rojo previamente aplicado
            $(row).find('.o_input_portal_product_description').css('border', '');
            $(row).find('.o_input_quantity').css('border', '');

            // Validar que la descripción no esté vacía
            if (!name) {
                $(row).find('.o_input_portal_product_description').css('border', '1px solid red');
                hasErrors = true;
            }

            // Validar que la cantidad no esté vacía o no sea menor o igual a cero
            if (!qty || qty <= 0) {
                $(row).find('.o_input_quantity').css('border', '1px solid red');
                hasErrors = true;
            }
        });

        return !hasErrors;
    },
    _onEditConfirm: function (doReload = true) {
        var rows = $('.items > tbody > tr.o_data_row');

        // Validar que los inputs requeridos no estén vacíos
        if (!this._validateInputs(rows)) {
            return false; // Detiene el envío del formulario si hay errores
        }

        rows.each((i, row) => {
            let product_id = $(row).find('.o_input_product').data('product-id');
            let name = $(row).find('.o_input_portal_product_description').val();
            let qty = $(row).find('.o_input_quantity').val();
            let uom_id = $(row).find('.o_input_uom').data('uom-id');
            let data_id = $(row).data('id'); // Obtener el atributo data-id

            // Si no tiene data-id, es una nueva línea
            if (!data_id) {
                this.Lines.push([0, 0, {
                    'product_id': product_id,
                    'name': name,
                    'portal_product_description': name,
                    'product_qty': qty,
                    'product_uom_id': uom_id,
                }]);
            } else {
                // Si actualiza ya no es necesario actualizar el name
                this.Lines.push([1, data_id, {
                    'id': data_id,
                    'product_id': product_id,
                    'portal_product_description': name,
                    'product_qty': qty,
                    'product_uom_id': uom_id,
                }]);
            }
        });

        // Guardar las líneas en el textarea (si todo está bien)
        $("textarea[name='line_ids']").val(JSON.stringify(this.Lines));

        // Actualizar el campo date_start al formato UTC
        $('.edit_form .date_start').val(this._parse_date($('.edit_form .date_start').val()));

        // Continuar con el flujo normal si no hay errores
        return true;
    },
    _validateAddProductLine: function (data) {
        var isValid = false;
        // Limpiar estilos de validación previamente aplicados
        $('.product_js_select2, .portal_description, .uom_js_select2').css('border', '');

        if (!data.product && !data.portal_product_description) {
            $('.product_js_select2').css('border', '1px solid red');
            $('.portal_description').css('border', '1px solid red');
            isValid = true;
        }

        if (data.product) {
            if (!data.uom) {
                $('.uom_js_select2').css('border', '1px solid red');
                isValid = true;
            }
        }

        return !isValid;
    },
    _onClickRequestLineAdd: function (doReload = true) {
        var product = $('.product_js_select2').select2('data');
        var uom = $('.uom_js_select2').select2('data');
        var qty = $('.edit_form .qty').val();
        var portal_description = $('.edit_form .portal_description').val();
        var data = {
            'product': product, 'uom': uom, 'product_qty': qty,
            'portal_product_description': portal_description
        };
        if (!this._validateAddProductLine(data)) {
            return false;
        }
        var tmpl_line = renderToElement('bf_portal_purchase_request.purchase_request_line', data);
        /*
        this.$ devuelve un objeto jQuery: Si this.$ es una función de jQuery, this.$('.table-body') devolverá un objeto jQuery,
        que no es compatible con el método appendChild. appendChild solo se puede utilizar en nodos DOM puros.
        Solución:
        Convierte el objeto jQuery en un nodo DOM utilizando [0] o .get(0). Modifica tu código como sigue:
        */
        var tbody = this.$('.table-body')[0];
        tbody.appendChild(tmpl_line);
        // Busca el primer input de descripción en la nueva fila
        var newRow = tbody.lastElementChild;
        var firstInput = newRow.querySelector('.o_input_portal_product_description');
        this._actualizarVisibilidadTabla();

        // Focaliza el cursor en el input de descripción
        if (firstInput) {
            firstInput.focus();
        }
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
                title: _t("Delete request."),
                body: _t("Are you sure you want to delete the request?"),
                confirmLabel: _t("Yes"),
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
                title: _t("Request approve."),
                body: _t("Are you sure you want to approve the request?"),
                confirmLabel: _t("Yes"),
                cancel: () => { }, // show cancel button
            })
        );
        if (confirmed) {
            window.location.href = ev.currentTarget.getAttribute('href');
        }
    },
});
