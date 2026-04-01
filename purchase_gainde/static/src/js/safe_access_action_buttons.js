/** @odoo-module **/

import { ActionMenus } from "@web/search/action_menus/action_menus";

export const ACTIONS_GROUP_NUMBER = 100;

function shouldIgnoreAccessActionButtonError(error) {
    const messages = [
        error?.message,
        error?.cause?.message,
        error?.data?.message,
    ].filter(Boolean);
    return messages.some((msg) =>
        String(msg).includes("/web/dataset/call_kw/user.management/access_search_action_button")
    );
}

function buildDefaultActions(props) {
    const actions = props?.items?.action || [];
    return actions.map((action) => {
        if (action.callback) {
            return Object.assign(
                { key: `action-${action.description}`, groupNumber: ACTIONS_GROUP_NUMBER },
                action
            );
        }
        return {
            action,
            description: action.name,
            key: action.id,
            groupNumber: action.groupNumber || ACTIONS_GROUP_NUMBER,
        };
    });
}

if (!ActionMenus.prototype._gaindeSafeAccessActionsPatched) {
    const originalGetActionItems = ActionMenus.prototype.getActionItems;

    ActionMenus.prototype.getActionItems = async function (props) {
        try {
            return await originalGetActionItems.call(this, props);
        } catch (error) {
            if (!shouldIgnoreAccessActionButtonError(error)) {
                throw error;
            }
            // Fallback: garder le menu d'actions standard sans filtrage access_users_manager
            return buildDefaultActions(props);
        }
    };

    ActionMenus.prototype._gaindeSafeAccessActionsPatched = true;
}
