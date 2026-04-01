/** @odoo-module **/
import { registry } from "@web/core/registry";

function allowPartnerCreateEdit(props) {
    const relation = props?.relation || props?.field?.relation || props?.record?.fields?.[props?.name]?.relation;
    const resModel = props?.record?.resModel || props?.record?.model?.name;
    const fieldName = props?.name;

    if (relation !== "res.partner") return;
    if (fieldName !== "partner_id") return;
    if (resModel !== "purchase.order" && resModel !== "sale.order") return;

    if ("canQuickCreate" in props) props.canQuickCreate = false;
    if ("canCreate" in props) props.canCreate = false;
    if ("canCreateEdit" in props) props.canCreateEdit = true;

    const ctx = props.context || {};
    if (resModel === "purchase.order") {
        props.context = { ...ctx, default_is_supplier: true };
    } else if (resModel === "sale.order") {
        props.context = { ...ctx, default_is_customer: true };
    }
}

const many2oneField = registry.category("fields").get("many2one");
if (many2oneField) {
    const OriginalComponent = many2oneField.component;
    const originalSetup = OriginalComponent.prototype.setup;

    OriginalComponent.prototype.setup = function (...args) {
        const result = originalSetup.apply(this, args);
        allowPartnerCreateEdit(this.props);

        if (this.onWillUpdateProps) {
            this._partner_exception_hook = (nextProps) => allowPartnerCreateEdit(nextProps);
            this.onWillUpdateProps(this._partner_exception_hook);
        }

        return result;
    };
}
