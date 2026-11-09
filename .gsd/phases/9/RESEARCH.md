# Phase 9 Research: Marketplace Domain Foundation

**Discovery level:** 0 (internal, follows the `masters/units` module recipe; no new dependencies)
**Date:** 2026-11-09

## Pattern to follow

`app/modules/masters/units/`: `domain/` (entities, enums, exceptions, `irepository.py`), `infrastructure/` (models, mapper,
repository with an `AccessScope` class), registration in `ModuleConfigurator._repo_config` and a `_<module>` classmethod.

Do not copy the units module's drift: `datetime.now(UTC)` imports, handlers importing infrastructure, or repositories
whose `update` silently returns when the row is outside scope.

## Schema (all new, `mkt_` prefix, DECISION-015)

| Table | Purpose | Key links |
|-------|---------|-----------|
| `mkt_categories` | Nested product categories | `parent_id` self, SET NULL |
| `mkt_animal_types` | Cow, buffalo, sheep, goat and others | |
| `mkt_animal_breeds` | Breeds per type | `animal_type_id` RESTRICT, unique (type, name) |
| `mkt_products` | Catalog items, soft delete | `seller_user_id` RESTRICT, `category_id` RESTRICT |
| `mkt_product_variants` | Sizes with MRP, price, stock | `product_id` CASCADE |
| `mkt_product_images` | Ordered gallery | `product_id` CASCADE |
| `mkt_animals` | Animal listings, soft delete | `seller_user_id` RESTRICT, type RESTRICT, breed SET NULL |
| `mkt_animal_images` | Ordered gallery | `animal_id` CASCADE |
| `mkt_banners` | Scheduled banners | |
| `mkt_home_sections` | Order and visibility of home sections | `category_id` SET NULL |
| `mkt_trending_tags` | Trending search links | |
| `mkt_settings` | One row of store settings | |
| `mkt_orders` | Guest or logged-in orders | `buyer_user_id` SET NULL |
| `mkt_order_items` | Lines with price and title snapshots | order CASCADE; product, variant and seller SET NULL |
| `mkt_enquiries` | Animal enquiries with title snapshot | animal and seller SET NULL |

## Decisions inside this phase

- **Images are rows, not JSON.** Galleries need ordering, a primary image and alt text. Cascades keep them tidy.
- **Stock is whole packs (`Integer`) per variant.** A pack is what a shopper buys, for example "1 L".
- **Money is `Numeric(12, 2)`** and `Decimal` in Python. Check constraints guard `price >= 0`, `mrp >= price` and `stock >= 0`.
- **Snapshots on orders and enquiries.** History stays readable after a listing changes or is removed.
- **Scope of code now:** models for every table, but entities and repositories only for the catalog this phase
  needs to prove the seller rule (categories, types, breeds, products, animals). Merchandising arrives in Phase 11,
  enquiries in Phase 13 and orders in Phase 14, each with its own use cases.

## Seller seam (DECISION-016)

- `SellerPolicy.SELLER_ROLES = frozenset({Role.SUPER_ADMIN})` is the only list of selling roles.
- `MarketplaceAccessScope`: Super Admin sees all listings; another seller sees only rows where `seller_user_id` is their id.
- Enabling Admin / Sub Admin later means adding those roles to the set and showing them the panel.
- `domain/` must not import `app.modules.administration.infrastructure`. `Role` lives in that module's `domain/enums.py`, which is allowed.

## Recycle Bin

Purging a user must delete their `mkt_products` and `mkt_animals` first, because of the RESTRICT links. Variants and
images cascade. Order lines and enquiries keep their snapshots through SET NULL, so other people's records survive.
Orders of a purged buyer also stay because a seller still needs them. This differs from the legacy purge, which deleted
buyer orders, because new orders carry their own buyer snapshot. The impact count adds new products and animals.

Note: a product row in an order keeps working through SET NULL, so purge order only has to respect products before users.

## Starter data

An idempotent seeder runs at startup after the Super Admin seeder. It stops as soon as the settings row exists, so
anything the Super Admin later edits or removes is not recreated, even if a whole table is emptied:
animal types (Cow, Buffalo, Goat, Sheep) with common breeds, root categories (Milk, Ghee & Butter, Curd & Paneer,
Coconut & Oils), one settings row, and default home sections. No fake products, animals or banners.

A seeder failure must not stop the dairy platform from starting: it logs and continues, like the worker start in `lifespan.py`.
