# Mise à jour du profil RCG — Accès Achats, Approbations & Répartitions analytiques

## Objectif

Donner au profil **RCG** (Responsable Contrôle de Gestion) les accès suivants :

1. **Accès au module Achats** (purchase.order)
2. **Accès à tous les bons de commande** (lecture + écriture)
3. **Peut voir toutes les Approbations**
4. **Peut modifier les lignes de répartitions analytiques**

---

## Fichiers modifiés

### 1. `models/user_management_extension.py`

#### `_gainde_get_domain_definitions()`

- **Ajout de 3 modèles** recherchés dans `ir.model` :
  - `purchase.order`
  - `purchase.order.line`
  - `approval.route.document.stage`

- **Mise à jour du mapping `"rcg"`** — avant, seul `purchase.request` était configuré. Désormais :

| Modèle                             | Lecture | Écriture | Création | Suppression | Domaine | Description                            |
|------------------------------------|---------|----------|----------|-------------|---------|----------------------------------------|
| `purchase.request`                 | ✅      | ✅       | ❌       | ❌          | filtré  | Demandes d'achat (inchangé)            |
| `purchase.order`                   | ✅      | ✅       | ❌       | ❌          | `[]`    | Tous les bons de commande              |
| `purchase.order.line`              | ✅      | ✅       | ❌       | ❌          | `[]`    | Toutes les lignes de bons de commande  |
| `approval.route.document.stage`    | ✅      | ❌       | ❌       | ❌          | `[]`    | Toutes les approbations (lecture seule) |
| `budget.analytic`                  | ✅      | ✅       | ❌       | ❌          | `[]`    | Répartitions analytiques               |

---

### 2. `models/user_profile_extension.py`

#### `create()` — Groupes implicites à la création du profil

- Ajout de `purchase.group_purchase_manager` dans les **implied groups** du profil RCG.
- Cela donne automatiquement accès au **module Achats** (menus, vues, bons de commande) à tous les utilisateurs rattachés au profil RCG.

**Avant :**
```python
# RCB et RCG portent aussi les droits budgétaires
if ptype == "rcb" and group_budget_user:
    implied_ids |= group_budget_user
if ptype == "rcg" and group_budget_admin:
    implied_ids |= group_budget_admin
```

**Après :**
```python
# RCG : achats manager (accès module Achats / bons de commande)
if ptype == "rcg" and group_purchase_manager:
    implied_ids |= group_purchase_manager
# RCB et RCG portent aussi les droits budgétaires
if ptype == "rcb" and group_budget_user:
    implied_ids |= group_budget_user
if ptype == "rcg" and group_budget_admin:
    implied_ids |= group_budget_admin
```

#### `write()` — Mise à jour dynamique quand le type de profil change vers RCG

- Ajout de `group_purchase_manager` dans le bloc `write()` gérant le changement de `profile_type` vers `"rcb"` ou `"rcg"`.
- Quand un profil existant est modifié pour devenir RCG, le groupe Achats Manager est ajouté automatiquement.

---

## Application sur une base existante

Pour les profils RCG **déjà existants** en base :

1. Aller sur la fiche **User Management** (pack) associée au profil RCG.
2. Cliquer sur le bouton **« Recharger les domaines »** (`action_gainde_reset_domain_access`).
3. Cela régénère les Domain Access avec les nouvelles règles.

Alternativement, une **mise à jour du module** `purchase_gainde` appliquera les groupes implicites pour les nouveaux profils créés.
