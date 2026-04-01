/** @odoo-module **/
import { registry } from "@web/core/registry";

/**
 * Fungsi helper untuk disable semua create
 */
function disableCreateProps(props) {
    if ('canCreateEdit' in props) props.canCreateEdit = false;
    if ('canQuickCreate' in props) props.canQuickCreate = false;
    if ('canCreate' in props) props.canCreate = false;
    return props;
}

/**
 * Patch Many2one
 */
const many2oneField = registry.category("fields").get("many2one");
if (many2oneField) {
    const OriginalComponent = many2oneField.component;
    const originalSetup = OriginalComponent.prototype.setup;

    OriginalComponent.prototype.setup = function(...args) {
        disableCreateProps(this.props);

        if (this.onWillUpdateProps) {
            this._disable_create_hook = (nextProps) => disableCreateProps(nextProps);
            this.onWillUpdateProps(this._disable_create_hook);
        }

        return originalSetup.apply(this, args);
    };
}

/**
 * Patch Many2many
 */
const many2manyField = registry.category("fields").get("many2many_tags");
if (many2manyField) {
    const OriginalComponent = many2manyField.component;
    const originalSetup = OriginalComponent.prototype.setup;

    OriginalComponent.prototype.setup = function(...args) {
        disableCreateProps(this.props);
        return originalSetup.apply(this, args);
    };
}

/**
 * Patch Many2many editable (color / tag editable)
 */
const many2manyEditableField = registry.category("fields").get("form.many2many_tags");
if (many2manyEditableField) {
    const OriginalComponent = many2manyEditableField.component;
    const originalSetup = OriginalComponent.prototype.setup;

    OriginalComponent.prototype.setup = function(...args) {
        disableCreateProps(this.props);
        return originalSetup.apply(this, args);
    };
}
