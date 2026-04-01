/** @odoo-module */

import { registry } from '@web/core/registry';
import { patch } from '@web/core/utils/patch';
import { KanbanController } from '@web/views/kanban/kanban_controller';

// Import the shared functionality from the list.js file
import { ExposeApiMixin, exposeApiAction } from './btn_expose_api_list';

// Patch the KanbanController to add expose API functionality
// Use a try-catch to handle both Odoo 16 and 17 patch function signatures
try {
    // First try with 3 parameters (Odoo 16 style)
    patch(KanbanController.prototype, 'BtnExposeApiKanbanController', {
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

    /**
     * Determine if the expose API button should be displayed
     * @returns {Boolean} - True if button should be displayed
     */
    displayExposeApi() {
        return ExposeApiMixin.displayExposeApi.call(this);
    },

    /**
     * Handle button click event
     */
    onExposeApiClick() {
        return ExposeApiMixin.onExposeApiClick.call(this);
    }
});
} catch (error) {
    // If the 3-parameter version fails, try with 2 parameters (Odoo 17 style)
    patch(KanbanController.prototype, {
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
