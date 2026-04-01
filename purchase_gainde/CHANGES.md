# Journal des changements — purchase_gainde (session 2026-03-12)

## Résumé exécutif

Correction d'une erreur `Uncaught (in promise) undefined` qui se produisait
dès la première frappe dans le champ **fournisseur** lors de la création
d'une commande alternative. La cause racine était un appel à `name_get()`
supprimé dans Odoo 18, présent dans `partner_tier_account`.

En parallèle, la logique de sélection de la route d'approbation
(`_get_default_approval_route_for_order`) a été **inversée** selon une
nouvelle règle métier, et des patches défensifs ont été ajoutés pour
sécuriser `access_users_manager`.

---

## 1. Inversion logique — `purchase_order.py`

**Fichier :** `models/purchase_order.py`

### Règle avant inversion
| Condition | Route assignée |
|-----------|---------------|
| Commande liée à une PR | `with_pr` (RCG → RCB → DA) |
| Commande **sans** PR   | `default` (RCB → DA) |

### Règle après inversion (état actuel)
| Condition | Route assignée |
|-----------|---------------|
| Commande **sans** PR | `with_pr` (RCG → RCB → DA) |
| Commande liée à une PR | `default` (RCB → DA) |

### Code modifié

```python
def _get_default_approval_route_for_order(self, company):
    """Choisit la route selon le lien à une demande d'achat.

    - Si la commande N'est PAS liée à une purchase.request : route RCG→RCB→DA.
    - Sinon (liée à une PR) : route par défaut (RCB→DA).
    """
    self.ensure_one()

    if not self._has_linked_purchase_request():
        route = self.env.ref(
            "purchase_gainde.xf_route_purchase_order_with_pr",
            raise_if_not_found=False,
        )
        if route and (not route.company_id or route.company_id.id == company.id):
            return route

    return self._get_default_approval_route_for_company(company)
```

### Cohérence avec `button_approve`

`button_approve` utilise `is_pr_route` basé sur la **route** (et non plus
sur la PR elle-même), ce qui reste cohérent après l'inversion :

```python
is_pr_route = order.approval_route_id == order.env.ref(
    "purchase_gainde.xf_route_purchase_order_with_pr",
    raise_if_not_found=False,
)
# True  => commande directe (sans PR) : seq1=RCG, seq2=RCB, seq3=DA
# False => commande issue d'une PR    : seq1=RCB, seq2=DA
```

---

## 2. Patch Odoo 18 — `name_get()` pour `res.partner`

**Fichier créé :** `models/res_partner_name_get_patch.py`

### Problème

`partner_tier_account/models/res_partner.py` contient :

```python
# line 34
res = super().name_get()   # AttributeError : 'super' object has no attribute 'name_get'

# line 59
results = partners.name_get() if partners else []  # idem
```

`name_get()` a été retiré de l'ORM dans Odoo 18. Lors d'une recherche dans
`name_search`, cela provoquait un `AttributeError` côté serveur, traduit en
`Uncaught (in promise) undefined` dans le navigateur.

### Solution

On réintroduit `name_get()` sur `res.partner` via `_inherit` dans
`purchase_gainde`, ce qui permet à l'appel `super().name_get()` de
`partner_tier_account` de se résoudre correctement dans le MRO.

```python
class ResPartnerNameGetPatch(models.Model):
    _inherit = "res.partner"

    def name_get(self):
        """Compat Odoo 18: name_get n'existe plus nativement."""
        if self.env.context.get("skip_tier_account_prefix"):
            return [(p.id, p.display_name or p.name or "") for p in self]

        result = []
        for partner in self:
            display = partner.display_name or partner.name or ""
            tier = (getattr(partner, "tier_account", "") or "").strip()
            if tier and not display.startswith(tier):
                display = f"{tier} - {display}"
            result.append((partner.id, display))
        return result
```

---

## 3. Patch défensif — `user.management.access_search_action_button`

**Fichier créé :** `models/access_user_management_patch.py`

### Problème

Le code original dans `access_users_manager` fait directement :

```python
cids = request.httprequest.cookies.get('cids').split('-')
```

Si le cookie `cids` est absent (multi-company non activé, session fraîche…),
cela lève un `AttributeError: 'NoneType' object has no attribute 'split'`.

### Solution

Override défensif dans `purchase_gainde` qui parse `cids` de façon sûre
et retombe sur `self.env.company.id` en cas d'absence.

```python
class UserManagement(models.Model):
    _inherit = "user.management"

    def access_search_action_button(self, model):
        cids_cookie = request.httprequest.cookies.get("cids") if request else None
        company_ids = [
            int(p) for p in str(cids_cookie or "").split("-")
            if p.strip().isdigit()
        ] or [self.env.company.id]
        # ... suite inchangée
```

---

## 4. Patch JS défensif — `ActionMenus.getActionItems`

**Fichier créé :** `static/src/js/safe_access_action_buttons.js`  
**Asset déclaré dans :** `__manifest__.py` → `web.assets_backend`

### Problème

`access_users_manager/static/src/js/hide_action_buttons.js` monkey-patche
`ActionMenus.prototype.getActionItems` et appelle le RPC
`user.management/access_search_action_button`. En cas d'erreur réseau
(`ConnectionLostError`) ou d'erreur Python côté serveur, la promesse se
rejette sans être rattrapée, produisant `Uncaught (in promise) undefined`.

### Solution

Wrapper try/catch autour de l'appel d'origine, avec fallback sur les actions
standard si l'erreur provient de ce RPC spécifique.

```js
if (!ActionMenus.prototype._gaindeSafeAccessActionsPatched) {
    const originalGetActionItems = ActionMenus.prototype.getActionItems;

    ActionMenus.prototype.getActionItems = async function (props) {
        try {
            return await originalGetActionItems.call(this, props);
        } catch (error) {
            if (!shouldIgnoreAccessActionButtonError(error)) {
                throw error;
            }
            return buildDefaultActions(props);  // fallback sans filtrage
        }
    };

    ActionMenus.prototype._gaindeSafeAccessActionsPatched = true;
}
```

---

## 5. Correction props OWL — `syn_disable_quick_create`

**Fichier modifié :**
`/opt/ci-stack/odoo/entreprise/syn_disable_quick_create/static/src/js/disable_relational_create.js`

### Problème

Le code original mutait directement `this.props` pendant le cycle `setup`/
`onWillUpdateProps` des composants OWL. Dans Odoo 18, les props OWL sont **en
lecture seule** (gelées) ; cette mutation silencieuse provoquait des
comportements imprévisibles lors des recherches many2one (debounce → timeout →
promesse rejetée).

### Solution

Patch de `field.extractProps` au lieu de muter `this.props`. Le composant
reçoit alors les props correctes dès l'extraction.

```js
function patchFieldExtractProps(fieldKey) {
    const field = registry.category("fields").get(fieldKey);
    if (!field || !field.extractProps || field.__gaindeDisableCreatePatched) return;

    const originalExtractProps = field.extractProps;
    field.extractProps = (...args) => disableCreateProps(originalExtractProps(...args));
    field.__gaindeDisableCreatePatched = true;
}

patchFieldExtractProps("many2one");
patchFieldExtractProps("many2many_tags");
patchFieldExtractProps("form.many2many_tags");
```

---

## 6. Correction `name_get` dans `eloapps_sequence_tiers`

**Fichier modifié :**
`/custom2/eloapps_sequence_tiers/models/res_partner.py`

`_compute_display_name` remplace l'ancien `name_get()` (supprimé en Odoo 18).
Appel à `super()._compute_display_name()` puis préfixage avec `compte_tiers`.

---

## 7. Mises à jour des fichiers de configuration

### `models/__init__.py`
Deux imports ajoutés :
```python
from . import access_user_management_patch
from . import res_partner_name_get_patch
```

### `__manifest__.py`
Asset JS ajouté dans `web.assets_backend` :
```python
'purchase_gainde/static/src/js/safe_access_action_buttons.js',
```

---

## Modules **non modifiés** (règle appliquée)

| Module | Raison |
|--------|--------|
| `access_users_manager` | Module de base — aucune modification |
| `access_users_managerdws` | Module de base — aucune modification |
| `ggaccess_users_manager` | Module de base — aucune modification |
| `partner_tier_account` | Module de base — aucune modification |

---

## Tableau récapitulatif des fichiers touchés

| Fichier | Action | Description |
|---------|--------|-------------|
| `purchase_gainde/models/purchase_order.py` | Modifié | Inversion `_get_default_approval_route_for_order` + commentaires `button_approve` |
| `purchase_gainde/models/res_partner_name_get_patch.py` | Créé | Compat Odoo 18 : réintroduit `name_get()` pour `partner_tier_account` |
| `purchase_gainde/models/access_user_management_patch.py` | Créé | Parsing défensif du cookie `cids` |
| `purchase_gainde/static/src/js/safe_access_action_buttons.js` | Créé | Try/catch JS sur `getActionItems` |
| `purchase_gainde/models/__init__.py` | Modifié | Imports des deux nouveaux patches Python |
| `purchase_gainde/__manifest__.py` | Modifié | Déclaration de l'asset JS dans `web.assets_backend` |
| `syn_disable_quick_create/.../disable_relational_create.js` | Modifié | Remplacement mutation `this.props` → patch `extractProps` |
| `eloapps_sequence_tiers/models/res_partner.py` | Modifié | Remplacement `name_get()` → `_compute_display_name()` |
