/** @odoo-module */

import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { ListController } from "@web/views/list/list_controller";
import { session } from "@web/session";
// v18
import { user } from "@web/core/user";

// Import version_info to check Odoo version
const version_info = session.server_version_info;    //[18, 0, 0, "final", 0, ""]

import { onWillStart } from '@odoo/owl';

function getResModel(target) {
    return (
      (target && 
       target.model && 
       target.model.rootParams && 
       target.model.rootParams.resModel) ||
      (target && 
       target.props && 
       target.props.resModel) ||
      null
    );
}

function getContext(target) {
    return (
      (target && 
       target.model && 
       target.model.rootParams && 
       target.model.rootParams.context) ||
      (target && 
       target.model && 
       target.model.config && 
       target.model.config.context) ||
      {}
    );
}

/**
 * Common function to handle the expose API button click
 * This function is shared between list and kanban views
 * 
 * @param {Event} ev - Click event (optional)
 * @param {Object} controller - Controller instance with required services
 * @returns {Promise} - Promise that resolves when the action is complete
 */
export async function exposeApiAction(ev, controller) {
    // Prevent event propagation if event exists
    if (ev) {
        ev.stopPropagation();
    }    

    const modelName = getResModel(controller);
    const context = getContext(controller);
    
    let result;
    // Use orm service if available (Odoo 18+), otherwise fall back to rpc
    if (controller.isOdoo18Plus) {
        // Using orm service (Odoo 18+)
        result = await controller.orm.call(
            'secure.api',
            'btn_expose_new_api',
            [modelName],
            { context: context }
        );
    } else {
        // Using rpc service (prior to Odoo 18)
        result = await controller.rpc('/web/dataset/call_kw/secure.api/btn_expose_new_api', {
            model: 'secure.api',
            method: 'btn_expose_new_api',
            args: [modelName],
            kwargs: {},
            context: context,
        });
    }
    
    controller.actionService.doAction(result);
}

/**
 * Mixin with common functionality for expose API feature
 * Can be used for both list and kanban controllers
 */
export const ExposeApiMixin = {
    /**
     * Setup required services and permissions
     */
    setupExposeApi() {
        // Check if we're in Odoo 18+ (has orm service) or prior version
        const isOdoo18Plus = version_info && version_info[0] >= 18;
        
        // Always get the action service
        this.actionService = useService('action');
        this.isOdoo18Plus = isOdoo18Plus;

        if (this.isOdoo18Plus) {
            // Use orm service in Odoo 18+
            this.orm = useService("orm");
            // In Odoo 18+, user service is removed, we'll use the orm service for group checks
        } else {
            // Use rpc service and user service in prior versions
            this.rpc = useService("rpc");
            this.user = useService("user");
        }
        
        onWillStart(async () => {
            // Guard: if a call fails (e.g. access error on an unexpected user type)
            // we fail-closed (button hidden) rather than breaking the view.
            try {
                if (this.isOdoo18Plus) {
                    this.isSystemAdmin = await user.hasGroup("base.group_system");
                    this.isExposeApiEnabled = await this.orm.call(
                        'ir.config_parameter',
                        'get_param',
                        ['secure_api.is_expose_api_on_view']
                    );
                } else {
                    // In prior versions, use the user service
                    this.isSystemAdmin = await this.user.hasGroup("base.group_system");
                    this.isExposeApiEnabled = await this.rpc('/web/dataset/call_kw/ir.config_parameter/get_param', {
                        model: 'ir.config_parameter',
                        method: 'get_param',
                        args: ['secure_api.is_expose_api_on_view'],
                        kwargs: {},
                    });
                }
            } catch (_e) {
                this.isSystemAdmin = false;
                this.isExposeApiEnabled = false;
            }
        });
    },

    /**
     * Determine if the expose API button should be displayed
     * @returns {Boolean} - True if button should be displayed
     */
    displayExposeApi() {
        const modelName = getResModel(this);
        return this.isExposeApiEnabled && 
               this.isSystemAdmin && 
               !modelName.startsWith("secure.api") && 
               !["ir.model"].includes(modelName);
    },

    /**
     * Handle button click event
     */
    onExposeApiClick() {
        exposeApiAction(null, this);
    }
};

// Patch the ListController to add expose API functionality
// Use a try-catch to handle both Odoo 16 and 17 patch function signatures
try {
    // First try with 3 parameters (Odoo 16 style)
    patch(ListController.prototype, 'BtnExposeApiListController', {
    setup() {
        try {
            this._super();
        } catch (error) {
            if (error instanceof TypeError && error.message.includes("this._super is not a function")) {
                super.setup();
            } else {
                throw error;
            }
        }
        ExposeApiMixin.setupExposeApi.call(this);
    },

    displayExposeApi() {
        return ExposeApiMixin.displayExposeApi.call(this);
    },

    onExposeApiClick() {
        return ExposeApiMixin.onExposeApiClick.call(this);
    }
});
} catch (error) {
    // If the 3-parameter version fails, try with 2 parameters (Odoo 17 style)
    patch(ListController.prototype, {
        setup() {
            try {
                this._super();
            } catch (error) {
                if (error instanceof TypeError && error.message.includes("this._super is not a function")) {
                    super.setup();
                } else {
                    throw error;
                }
            }
            ExposeApiMixin.setupExposeApi.call(this);
        },

        displayExposeApi() {
            return ExposeApiMixin.displayExposeApi.call(this);
        },

        onExposeApiClick() {
            return ExposeApiMixin.onExposeApiClick.call(this);
        }
    });
}
