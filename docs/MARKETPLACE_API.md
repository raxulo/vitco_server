# Marketplace API (v1)

The public store API used by the website and the mobile app: browse products and animals, send an enquiry
for an animal, price a cart, place a Cash on Delivery order and track it.

Every example below is a real response from the API (demo data, shortened where a list is long).

---

## Contents

1. [Basics](#1-basics)
2. [Response format](#2-response-format)
3. [Errors](#3-errors)
4. [Store](#4-store)
5. [Products](#5-products)
6. [Animals](#6-animals)
7. [Animal enquiry](#7-animal-enquiry)
8. [Cart and checkout](#8-cart-and-checkout)
9. [Order tracking](#9-order-tracking)
10. [Values and enums](#10-values-and-enums)
11. [App flow checklist](#11-app-flow-checklist)
12. [Endpoint summary](#12-endpoint-summary)

---

## 1. Basics

| Item | Value |
|------|-------|
| Base path | `/api/v1/marketplace` |
| Format | JSON in, JSON out (`Content-Type: application/json`) |
| Login | **Not needed.** Every endpoint is public. |
| Money | Strings with 2 decimals, e.g. `"42.00"`. Parse them as decimals, never as floats. |
| Dates | ISO 8601 without a timezone, in Indian time (IST), e.g. `"2026-11-13T00:10:38.440925"` |
| Images | Paths such as `/api/v1/media/product/<id>.webp`. Put the server address in front: `https://<host>/api/v1/media/...`. They are public. |
| IDs in URLs | Products, categories, animal types and animals use a readable `slug` (e.g. `demo-a2-gir-cow-milk`). Product sizes (`variant_id`) and breeds (`id`) use UUIDs. |

**Optional login.** If the app sends a logged-in user's token (`Authorization: Bearer <access_token>`) when it
places an order, the order is linked to that user. Without a token the order is placed as a guest. Nothing
else changes.

**Rate limits.** Three actions are limited **per client IP address, per 10 minutes**:

| Action | Limit |
|--------|-------|
| `POST /animals/{slug}/enquiries` | 10 |
| `POST /orders` | 20 |
| `POST /orders/track` | 20 |

Above the limit the API answers `429` (see [Errors](#3-errors)). Browsing is not limited. The counts are shared
with the website, and many phones on one mobile network can share an IP, which is why the limits are generous.

**Not in this API:** online payment and buyer accounts (Cash on Delivery only); listing, changing or cancelling
orders (sellers do this in the Control Center); managing listings (the Control Center has no REST API).

---

## 2. Response format

### Single record

```json
{
  "status": true,
  "code": 200,
  "message": "Store fetched successfully",
  "data": { }
}
```

`code` is the same as the HTTP status (`200`, or `201` for an enquiry or a new order).

### List

```json
{
  "status": true,
  "code": 200,
  "message": "Products fetched successfully",
  "items": [ ],
  "limit": 24,
  "offset": 0,
  "total": 12,
  "pages": 1,
  "next_page": null,
  "has_more": false
}
```

| Field | Meaning |
|-------|---------|
| `items` | The records on this page |
| `limit`, `offset` | What was asked for |
| `total` | Records matching the filters, on all pages |
| `pages` | Number of pages for this `limit` (at least 1) |
| `next_page` | Next page number (1-based), or `null` on the last page |
| `has_more` | `true` when another page exists. For the next page, send `offset = offset + limit`. |

Lists without paging (categories, animal types, breeds) use the same shape with every record on one page.

---

## 3. Errors

### Business errors: `success: false`

```json
{
  "success": false,
  "error": {
    "code": "MARKETPLACE_PRODUCT_NOT_FOUND",
    "message": "Product not found.",
    "details": {}
  }
}
```

**Form errors** (status `422`, code `MARKETPLACE_INVALID_LISTING`) put one message per field in `details`.
Show each message under its field. The key `form` is a message for the whole form:

```json
{
  "success": false,
  "error": {
    "code": "MARKETPLACE_INVALID_LISTING",
    "message": "Please correct the highlighted fields.",
    "details": {
      "buyer_phone": "Please enter a 10 digit mobile number.",
      "pincode": "Please enter a 6 digit pincode."
    }
  }
}
```

### Malformed request: `detail`

A missing required field, a wrong type, or a value outside its limits (for example `limit=500`) is rejected
before any business rule runs. The status is `422`, with a different shape:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "buyer_name"],
      "msg": "Field required",
      "input": { "buyer_phone": "9876543210" }
    }
  ]
}
```

`loc` is where the value was (`body` or `query`) and the field name. These errors mean the app sent something
it should not have; check the request against this document.

### Error codes

| HTTP | `error.code` | When | What the app should do |
|------|--------------|------|------------------------|
| 404 | `MARKETPLACE_PRODUCT_NOT_FOUND` | Unknown, unpublished or archived product slug | Show "not available" |
| 404 | `MARKETPLACE_ANIMAL_NOT_FOUND` | Unknown or hidden animal slug | Show "not available" |
| 404 | `MARKETPLACE_ORDER_NOT_FOUND` | Tracking: wrong reference **or** wrong phone (the API never says which) | "No order found for this reference and phone number" |
| 409 | `MARKETPLACE_ANIMAL_NOT_AVAILABLE` | Enquiry for a sold animal | Show "This animal has been sold" |
| 409 | `MARKETPLACE_OUT_OF_STOCK` | Stock ran out while the order was being placed | Call `/cart/quote` again and show the updated cart |
| 422 | `MARKETPLACE_INVALID_LISTING` | Form rules (see each endpoint) | Show `details` under the fields |
| 429 | `MARKETPLACE_TOO_MANY_REQUESTS` | Rate limit reached | Wait `Retry-After` seconds (header, also `details.retry_after`) |
| 503 | `MARKETPLACE_BUSY` | The server was too busy to place the order; nothing was saved | Wait `Retry-After` seconds and send the **same** request again |
| 422 | (no code, `detail` list) | Malformed request | Fix the request |

`429` example (header `Retry-After: 412`):

```json
{
  "success": false,
  "error": {
    "code": "MARKETPLACE_TOO_MANY_REQUESTS",
    "message": "Too many attempts. Please wait a few minutes and try again.",
    "details": { "retry_after": 412 }
  }
}
```

---

## 4. Store

### `GET /store`

Store name, contact details, delivery rules and policies. Load it once when the app opens, and use it for the
cart screen and the policy pages.

```json
{
  "status": true,
  "code": 200,
  "message": "Store fetched successfully",
  "data": {
    "store_name": "Vitco Marketplace",
    "tagline": "Honest dairy animals and fresh farm products, sold directly.",
    "logo_url": null,
    "support_phone": "9000000000",
    "whatsapp_number": "919000000000",
    "support_email": "hello@example.com",
    "address": "Jaipur, Rajasthan",
    "delivery_charge": "40.00",
    "free_delivery_above": "499.00",
    "min_order_amount": "100.00",
    "cod_enabled": true,
    "serviceable_pincodes": [],
    "is_store_open": true,
    "closed_message": null,
    "policies": {
      "shipping": "Orders inside our delivery area usually arrive the next morning.",
      "returns": "Tell us within 24 hours if a product arrives damaged and we will replace it.",
      "terms": "Animals are sold directly by the seller; please visit and inspect before you buy.",
      "privacy": "We use your phone number and address only to deliver your order."
    }
  }
}
```

| Field | Meaning |
|-------|---------|
| `whatsapp_number` | With country code, ready for `https://wa.me/<number>` |
| `delivery_charge` | Charged when the subtotal is below `free_delivery_above` |
| `free_delivery_above` | Subtotal for free delivery; `null` = delivery is never free |
| `min_order_amount` | Smallest subtotal that can be ordered (`"0.00"` = no minimum) |
| `cod_enabled` | Cash on Delivery is on. It is the only payment method; when `false`, orders cannot be placed. |
| `serviceable_pincodes` | Pincodes the store delivers to. **Empty list = every pincode.** |
| `is_store_open` / `closed_message` | When closed, orders are refused; show `closed_message` |
| `policies` | Keys `shipping`, `returns`, `terms`, `privacy`. A key is missing when that policy is empty. |

### `GET /home`

Everything the home screen needs, arranged by the admin in the Control Center.

```json
{
  "status": true,
  "code": 200,
  "message": "Home fetched successfully",
  "data": {
    "store": { "...": "same object as GET /store" },
    "trending_tags": [
      { "label": "Gir cow", "url": "/marketplace/animals?search=gir" },
      { "label": "Desi ghee", "url": "/marketplace/products?search=ghee" }
    ],
    "hero_banners": [
      {
        "title": "Milk you can trust, from cows you can meet",
        "subtitle": "Choose healthy Gir and Sahiwal cows with their milk records.",
        "cta_label": "Browse animals",
        "cta_url": "/marketplace/animals",
        "image_url": "/api/v1/media/banner/984133790d074243a291aa9f0a0730c6.webp",
        "mobile_image_url": "/api/v1/media/banner/58e2dd42a94c4973975b740e01fdf4f0.webp"
      }
    ],
    "blocks": [
      {
        "section_type": "CATEGORIES",
        "title": "Shop by category",
        "subtitle": null,
        "category_slug": null,
        "categories": [ { "name": "Milk", "slug": "milk", "image_url": null } ],
        "products": [],
        "animals": [],
        "banners": []
      },
      {
        "section_type": "FEATURED_ANIMALS",
        "title": "Featured animals",
        "subtitle": null,
        "category_slug": null,
        "categories": [],
        "products": [],
        "animals": [ { "...": "animal card, see section 6" } ],
        "banners": []
      }
    ]
  }
}
```

- `hero_banners`: the top carousel. On a phone use `mobile_image_url` when it is set, otherwise `image_url`.
- `blocks`: show them **in the order received**. Each block fills only the list that matches its `section_type`:

| `section_type` | Filled list | Notes |
|----------------|-------------|-------|
| `CATEGORIES` | `categories` | |
| `TRENDING` | `products` and `animals` | Items the admin marked trending |
| `FEATURED_ANIMALS` | `animals` | |
| `FEATURED_PRODUCTS` | `products` | |
| `MIDDLE_BANNERS` | `banners` | Banner objects as in `hero_banners` |
| `CATEGORY_PRODUCTS` | `products` | Products of `category_slug`; a "See all" link can open the product list with `category=<category_slug>` |

  A block with nothing to show is left out by the server. Ignore any `section_type` the app does not know, so
  new types never break an older app.

- **Links** (`trending_tags[].url`, `cta_url`) are website paths. Map them to app screens:

| Link | App screen |
|------|-----------|
| `/marketplace/products?...` | Product list, with the same query values as filters (`search`, `category`, ...) |
| `/marketplace/products/<slug>` | Product detail |
| `/marketplace/animals?...` | Animal list, with the same query values as filters |
| `/marketplace/animals/<slug>` | Animal detail |
| `http(s)://...` | Open in the browser |

### `GET /categories`

Active **top-level** product categories, in the admin's order. Sub-categories are not listed, but filtering by a
top-level `slug` also returns the products of its sub-categories. Use `slug` as the `category` filter.

```json
{
  "status": true, "code": 200, "message": "Categories fetched successfully",
  "items": [
    { "name": "Milk", "slug": "milk", "image_url": null },
    { "name": "Ghee & Butter", "slug": "ghee-butter", "image_url": null }
  ],
  "limit": 4, "offset": 0, "total": 4, "pages": 1, "next_page": null, "has_more": false
}
```

### `GET /animal-types`

Active animal types (Cow, Buffalo, ...). Use `slug` as the `type` filter.

```json
{
  "status": true, "code": 200, "message": "Animal types fetched successfully",
  "items": [
    { "name": "Cow", "slug": "cow", "image_url": null },
    { "name": "Buffalo", "slug": "buffalo", "image_url": null }
  ],
  "limit": 4, "offset": 0, "total": 4, "pages": 1, "next_page": null, "has_more": false
}
```

### `GET /animal-types/{slug}/breeds`

Breeds of one type, for the breed filter. Use `id` as the `breed` filter. An unknown type returns an empty list.

```json
{
  "status": true, "code": 200, "message": "Breeds fetched successfully",
  "items": [
    { "id": "31b3a299-dcac-4707-a8ae-e63b43aae37c", "name": "Gir" },
    { "id": "1d8fb5fd-7b59-4c0f-8d61-e6aa1dc2d72b", "name": "Sahiwal" }
  ],
  "limit": 6, "offset": 0, "total": 6, "pages": 1, "next_page": null, "has_more": false
}
```

---

## 5. Products

Only published products are returned. Archived or draft products answer `404`.

### `GET /products` and `POST /products/list`

The same search. Send the filters as query parameters to `GET /products`, or as a JSON body to
`POST /products/list`. All filters are optional.

| Filter | Type | Rule |
|--------|------|------|
| `search` | string, max 100 | Matches the title, brand or short description (case-insensitive) |
| `category` | string | Category `slug`. **Includes its sub-categories.** An unknown slug gives an empty list. |
| `min_price`, `max_price` | decimal ≥ 0 | On the card price (the default size) |
| `in_stock` | boolean, default `false` | `true` = only products with a size in stock |
| `sort` | `newest` (default), `price_asc`, `price_desc` | |
| `limit` | 1–100, default 24 | |
| `offset` | ≥ 0, default 0 | |

```http
GET /api/v1/marketplace/products?category=milk&sort=price_asc&limit=2
```

```http
POST /api/v1/marketplace/products/list
Content-Type: application/json

{ "search": "milk", "in_stock": true, "limit": 2, "offset": 0 }
```

Response: a list of **product cards**.

```json
{
  "status": true,
  "code": 200,
  "message": "Products fetched successfully",
  "items": [
    {
      "slug": "demo-sweet-lassi",
      "title": "Sweet Lassi",
      "brand": "Vitco Dairy",
      "short_description": "Chilled, thick and lightly sweet.",
      "price": "25.00",
      "mrp": "30.00",
      "discount_percent": 16,
      "size": "200 ml",
      "other_sizes": 0,
      "in_stock": true,
      "image_url": "/api/v1/media/product/5c29ad8d40bd45ff8afeda26c8ed0936.webp",
      "image_alt": "Sweet Lassi"
    }
  ],
  "limit": 2, "offset": 0, "total": 12, "pages": 6, "next_page": 2, "has_more": true
}
```

| Card field | Meaning |
|------------|---------|
| `price`, `mrp`, `discount_percent`, `size` | Of the default size |
| `other_sizes` | How many more sizes exist ("+1 more size") |
| `in_stock` | At least one size can be bought |
| `image_url`, `image_alt` | First image; `null` when there is none |

### `GET /products/{slug}`

Product detail and up to a few related products.

```json
{
  "status": true,
  "code": 200,
  "message": "Product fetched successfully",
  "data": {
    "product": {
      "slug": "demo-a2-gir-cow-milk",
      "title": "A2 Gir Cow Milk",
      "brand": "Vitco Farms",
      "short_description": "Fresh farm milk, chilled and delivered the same morning.",
      "description": "Milk from our Gir cows, chilled right after milking and packed the same day.\n\nBoil before use. Keep refrigerated.",
      "category_name": "Milk",
      "category_slug": "milk",
      "specifications": [
        { "label": "Shelf life", "value": "2 days, refrigerated" },
        { "label": "Fat", "value": "4.5%" }
      ],
      "sizes": [
        {
          "variant_id": "1a9638b6-4853-4c1b-8e8e-8fa7c3b92218",
          "name": "500 ml",
          "price": "42.00",
          "mrp": "45.00",
          "discount_percent": 6,
          "in_stock": true,
          "is_default": true,
          "few_left": null
        },
        {
          "variant_id": "fe384472-3383-4c1a-a0fe-7260cbe11aff",
          "name": "1 L",
          "price": "78.00",
          "mrp": "85.00",
          "discount_percent": 8,
          "in_stock": true,
          "is_default": false,
          "few_left": null
        }
      ],
      "images": [
        { "url": "/api/v1/media/product/dc5bb0ce1e614f80b687cf1f6ec9e134.webp", "alt": "A2 Gir Cow Milk" }
      ]
    },
    "related": [ { "...": "product card" } ]
  }
}
```

- `description` is plain text; a blank line (`\n\n`) separates paragraphs.
- `sizes`: what the buyer chooses. Preselect the one with `is_default: true`. **The cart uses `variant_id`.**
- `few_left`: the number left when stock is low ("Only 3 left"), otherwise `null`. The exact stock is never shown.

---

## 6. Animals

Published and reserved animals appear in lists. A sold animal still opens by its slug (its page says sold), but
it cannot receive enquiries.

**Animals are never added to the cart.** The buyer calls, sends a WhatsApp message (numbers from `/store`), or
sends an enquiry ([section 7](#7-animal-enquiry)).

### `GET /animals` and `POST /animals/list`

The same search; query parameters for `GET`, a JSON body for `POST`. All filters are optional.

| Filter | Type | Rule |
|--------|------|------|
| `search` | string, max 100 | Matches the title, breed, type or district |
| `type` | string | Animal type `slug`; unknown = empty list |
| `breed` | UUID | Breed `id` from `/animal-types/{slug}/breeds` |
| `min_price`, `max_price` | decimal ≥ 0 | |
| `min_milk` | decimal ≥ 0 | Litres per day, at least |
| `lactation` | 1–4 | Lactation number; **4 means 4 or more** |
| `location` | string, max 100 | Matches village, district or state |
| `sort` | `newest` (default), `price_asc`, `price_desc`, `milk_desc` | `milk_desc` puts animals without a milk figure last |
| `limit` | 1–100, default 24 | |
| `offset` | ≥ 0, default 0 | |

```http
GET /api/v1/marketplace/animals?type=cow&sort=milk_desc&limit=2
```

Response: a list of **animal cards**.

```json
{
  "status": true,
  "code": 200,
  "message": "Animals fetched successfully",
  "items": [
    {
      "slug": "demo-hf-cross-high-yield",
      "title": "HF cross cow, high yield",
      "type_name": "Cow",
      "breed_name": "HF Cross",
      "status": "PUBLISHED",
      "price": "95000.00",
      "is_negotiable": false,
      "milk_litres_per_day": "22.00",
      "lactation_number": 3,
      "age_months": 54,
      "location": "Karnal, Haryana",
      "image_url": "/api/v1/media/animal/5953fa500b324774b4d3f348bfd14d18.webp",
      "image_alt": "HF cross cow, high yield"
    }
  ],
  "limit": 2, "offset": 0, "total": 4, "pages": 2, "next_page": 2, "has_more": true
}
```

- `status`: `PUBLISHED` (available) or `RESERVED` (show a "Reserved" badge).
- `location`: district and state for display. `breed_name`, `milk_litres_per_day`, `lactation_number`, `age_months` may be `null`.

### `GET /animals/{slug}`

```json
{
  "status": true,
  "code": 200,
  "message": "Animal fetched successfully",
  "data": {
    "animal": {
      "slug": "demo-gir-cow-second-lactation",
      "title": "Gir cow, second lactation",
      "type_name": "Cow",
      "type_slug": "cow",
      "breed_name": "Gir",
      "status": "PUBLISHED",
      "gender": "FEMALE",
      "price": "85000.00",
      "is_negotiable": true,
      "age_months": 48,
      "lactation_number": 2,
      "milk_litres_per_day": "14.50",
      "fat_percent": "4.80",
      "pregnancy_status": "NOT_PREGNANT",
      "pregnancy_months": null,
      "calf_details": "Female calf, 3 months old, can be sold together",
      "health_notes": "Healthy, active and eating well. Checked by a local vet last month.",
      "vaccination_notes": "FMD and HS vaccines are up to date. Card available.",
      "village": "Chomu",
      "district": "Jaipur",
      "state": "Rajasthan",
      "description": "A calm, well-kept Gir cow in her second lactation.\n\nMilk records are available and you are welcome to visit before buying.",
      "images": [
        { "url": "/api/v1/media/animal/e10f7b8a2cad413a94be020500beb3d3.webp", "alt": "Gir cow, second lactation" }
      ]
    },
    "similar": [ { "...": "animal card" } ]
  }
}
```

- `status` can also be `SOLD` here: hide the enquiry form and show "Sold".
- `pregnancy_months` is set only when `pregnancy_status` is `PREGNANT`.
- Every text field except `slug`, `title`, `type_name`, `type_slug`, `status`, `gender`, `price` and
  `pregnancy_status` may be `null`; hide the row when it is.

---

## 7. Animal enquiry

### `POST /animals/{slug}/enquiries`

The buyer leaves a name and phone number; the seller sees the enquiry in the Control Center and calls back.

Request:

```json
{
  "buyer_name": "Ramesh Patel",
  "buyer_phone": "+91 98765 43210",
  "location": "Anand",
  "message": "Is she still available?"
}
```

| Field | Required | Rule |
|-------|----------|------|
| `buyer_name` | yes | At least 2 characters, max 120 |
| `buyer_phone` | yes | An Indian mobile number: 10 digits starting with 6–9. `+91`, `91`, a leading `0`, spaces, dashes and brackets are accepted and removed. Max 20 characters. |
| `location` | no | Max 200 |
| `message` | no | Max 1000 |

Response `201`:

```json
{ "status": true, "code": 201, "message": "Enquiry sent successfully", "data": { "received": true } }
```

- Sending again from the same phone while the earlier enquiry is still open also answers `201`, but does not
  create a second enquiry.
- Errors: `422` with `details.buyer_name` / `details.buyer_phone`; `404` unknown animal; `409`
  `MARKETPLACE_ANIMAL_NOT_AVAILABLE` sold animal; `429` rate limit.

```json
{
  "success": false,
  "error": {
    "code": "MARKETPLACE_INVALID_LISTING",
    "message": "Please correct the highlighted fields.",
    "details": {
      "buyer_name": "Please enter your name.",
      "buyer_phone": "Please enter a 10 digit mobile number."
    }
  }
}
```

---

## 8. Cart and checkout

**The app keeps the cart on the phone** (a list of `variant_id` + `quantity`). The server keeps no cart. Before
showing the cart and before placing the order, ask the server for today's prices and stock.

Only Cash on Delivery exists today.

### `POST /cart/quote`

Request:

```json
{
  "items": [
    { "variant_id": "1a9638b6-4853-4c1b-8e8e-8fa7c3b92218", "quantity": 2 },
    { "variant_id": "8401f993-1ac0-483e-b2e4-eced162228e8", "quantity": 1 }
  ]
}
```

| Field | Rule |
|-------|------|
| `items` | 0–30 lines; each `variant_id` once |
| `quantity` | 1–50 per line |

Response (here the app also sent a third `variant_id` that is no longer sold):

```json
{
  "status": true,
  "code": 200,
  "message": "Cart priced successfully",
  "data": {
    "lines": [
      {
        "variant_id": "1a9638b6-4853-4c1b-8e8e-8fa7c3b92218",
        "slug": "demo-a2-gir-cow-milk",
        "title": "A2 Gir Cow Milk",
        "size": "500 ml",
        "price": "42.00",
        "mrp": "45.00",
        "quantity": 2,
        "line_total": "84.00",
        "image_url": "/api/v1/media/product/dc5bb0ce1e614f80b687cf1f6ec9e134.webp",
        "reduced_from": null,
        "is_out_of_stock": false,
        "max_quantity": 50
      },
      {
        "variant_id": "8401f993-1ac0-483e-b2e4-eced162228e8",
        "slug": "demo-fresh-toned-milk",
        "title": "Fresh Toned Milk",
        "size": "500 ml",
        "price": "28.00",
        "mrp": "30.00",
        "quantity": 1,
        "line_total": "28.00",
        "image_url": "/api/v1/media/product/d2c527b89fe146e8b13ee1f153b2ec2e.webp",
        "reduced_from": null,
        "is_out_of_stock": false,
        "max_quantity": 50
      }
    ],
    "removed_count": 1,
    "subtotal": "112.00",
    "delivery_charge": "40.00",
    "total": "152.00",
    "min_order_amount": "100.00",
    "below_minimum_by": "0",
    "free_delivery_gap": "387.00",
    "is_store_open": true,
    "cod_enabled": true,
    "can_check_out": true
  }
}
```

| Field | Meaning and what to do |
|-------|------------------------|
| `lines` | The lines still on sale, with today's price. **Replace the app's cart with these.** |
| `removed_count` | Lines dropped because the product is no longer sold. If above 0, remove the missing `variant_id`s from the app's cart and tell the buyer. |
| `quantity` / `reduced_from` | When stock is lower than asked, `quantity` is what can be bought and `reduced_from` what was asked ("Only 3 available"). Otherwise `reduced_from` is `null`. |
| `is_out_of_stock` | `quantity` is 0. The line is shown but not charged; the buyer should remove it. |
| `max_quantity` | Highest quantity for the stepper (stock, at most 50) |
| `subtotal`, `delivery_charge`, `total` | What the buyer pays. `delivery_charge` is 0 when the subtotal reaches `free_delivery_above`, or when nothing can be bought. |
| `below_minimum_by` | How much more to add to reach `min_order_amount` (`"0"` when reached) |
| `free_delivery_gap` | How much more for free delivery (`"0"` when free or not offered) |
| `can_check_out` | `true` when there is something to buy, the store is open, COD is on and the minimum is reached |

> Before placing the order the cart must be **clean**: `removed_count` is 0 and no line has `reduced_from`.
> Otherwise `POST /orders` answers "Some items in your cart changed". Update the app's cart from this
> response (remove dropped lines, take the reduced quantities) and quote again.

### `POST /orders`

Request:

```json
{
  "items": [
    { "variant_id": "1a9638b6-4853-4c1b-8e8e-8fa7c3b92218", "quantity": 2 },
    { "variant_id": "8401f993-1ac0-483e-b2e4-eced162228e8", "quantity": 1 }
  ],
  "buyer_name": "Ramesh Patel",
  "buyer_phone": "9876543210",
  "address_line": "12, Gandhi Chowk, Near Bus Stand",
  "city": "Anand",
  "state": "Gujarat",
  "pincode": "388001",
  "notes": "Call before coming",
  "checkout_token": "9659719e-8ac1-482e-84cd-b423d93ee30d",
  "expected_total": "152.00"
}
```

| Field | Required | Rule |
|-------|----------|------|
| `items` | yes | 1–30 lines, quantity 1–50, the same lines the buyer saw in the last quote |
| `buyer_name` | yes | At least 2 characters, max 120 |
| `buyer_phone` | yes | Indian mobile, same rule as the enquiry. It is also needed to track the order. |
| `address_line` | yes | At least 10 characters ("house and area"), max 500 |
| `city`, `state` | no | Max 100 each |
| `pincode` | yes | Exactly 6 digits, and served by the store (`serviceable_pincodes`; empty = all) |
| `notes` | no | Max 500 |
| `checkout_token` | yes | A UUID the app creates **once when the checkout screen opens**; see below |
| `expected_total` | yes | The `total` from the last quote the buyer saw, as a string |

Response `201`:

```json
{
  "status": true,
  "code": 201,
  "message": "Order placed successfully",
  "data": { "order_ref": "VT-261113-KLAKC7", "total": "152.00", "status": "PLACED" }
}
```

Show `order_ref` to the buyer and save it (with the phone number) on the phone for tracking.
The format is `VT-<yymmdd>-<6 letters/digits>`.

#### `checkout_token`: no double orders

Generate a new UUID (v4) when the checkout screen opens, and keep it until an order is placed. If the network
drops or the buyer taps "Place order" twice, **send the same request again with the same token**: the server
returns the **same** `order_ref` (`201`) and never creates a second order. Make a new token only for a new
checkout.

#### `expected_total`: no surprise prices

If prices, stock or the delivery charge changed after the last quote, the server refuses the order instead of
charging a different amount:

```json
{
  "success": false,
  "error": {
    "code": "MARKETPLACE_INVALID_LISTING",
    "message": "Please correct the highlighted fields.",
    "details": { "form": "Prices changed since you opened this page. Please check the new total." }
  }
}
```

Quote the cart again, show the new total, and let the buyer confirm.

#### Order errors

| Status | Details | Cause |
|--------|---------|-------|
| 422 | `buyer_name`, `buyer_phone`, `address_line`, `pincode` | Field rules above; `pincode` also says "Sorry, we do not deliver to this pincode yet." |
| 422 | `form`: "We are not taking orders right now." (or the store's `closed_message`) | Store closed |
| 422 | `form`: "Cash on Delivery is not available right now." | COD switched off |
| 422 | `form`: "Your cart is empty or its items are out of stock." | Nothing payable |
| 422 | `form`: "Some items in your cart changed. Please review it and try again." | A line was removed or reduced; quote again |
| 422 | `form`: "Your order is below the minimum order amount." | Below `min_order_amount` |
| 422 | `form`: "Prices changed since you opened this page. Please check the new total." | `expected_total` differs from the server total |
| 409 | `MARKETPLACE_OUT_OF_STOCK` | Another buyer took the last stock a moment earlier; quote again |
| 429 | `MARKETPLACE_TOO_MANY_REQUESTS` | Rate limit |
| 503 | `MARKETPLACE_BUSY` | Not placed; retry the same request after `Retry-After` |

The field checks (name, phone, address, pincode) run first and are reported together; the cart checks come after.

---

## 9. Order tracking

### `POST /orders/track`

Needs **both** the order reference and the phone number used for the order. A wrong value in either gives the
same `404`, so a reference alone reveals nothing.

Request:

```json
{ "order_ref": "VT-261113-KLAKC7", "phone": "+91 9876543210" }
```

| Field | Rule |
|-------|------|
| `order_ref` | Max 30 characters |
| `phone` | Max 20; the same formats as `buyer_phone` are accepted |

Response:

```json
{
  "status": true,
  "code": 200,
  "message": "Order fetched successfully",
  "data": {
    "order_ref": "VT-261113-KLAKC7",
    "status": "PLACED",
    "payment_method": "COD",
    "payment_status": "PENDING",
    "pincode": "388001",
    "subtotal": "112.00",
    "delivery_charge": "40.00",
    "total": "152.00",
    "cancel_reason": null,
    "created_at": "2026-11-13T00:10:38.440925",
    "lines": [
      {
        "product_title": "A2 Gir Cow Milk",
        "variant_name": "500 ml",
        "unit_price": "42.00",
        "quantity": 2,
        "line_total": "84.00"
      },
      {
        "product_title": "Fresh Toned Milk",
        "variant_name": "500 ml",
        "unit_price": "28.00",
        "quantity": 1,
        "line_total": "28.00"
      }
    ]
  }
}
```

- The buyer's name and address are deliberately not returned.
- Prices are the ones at the time of the order, even if the product's price changed later.
- `cancel_reason` is set when `status` is `CANCELLED`.

Not found:

```json
{
  "success": false,
  "error": { "code": "MARKETPLACE_ORDER_NOT_FOUND", "message": "Order not found.", "details": {} }
}
```

---

## 10. Values and enums

| Field | Values |
|-------|--------|
| Order `status` | `PLACED` → `CONFIRMED` → `PACKED` → `OUT_FOR_DELIVERY` → `DELIVERED`, or `CANCELLED` at any step before delivery. The seller moves it in the Control Center. Show the first five as a progress bar. |
| `payment_method` | `COD` |
| `payment_status` | `PENDING`, `PAID`, `REFUNDED` |
| Animal `status` | `PUBLISHED` (available), `RESERVED`, `SOLD` (detail page only) |
| `gender` | `FEMALE`, `MALE` |
| `pregnancy_status` | `NOT_PREGNANT`, `PREGNANT`, `UNKNOWN` |
| Home `section_type` | `CATEGORIES`, `TRENDING`, `FEATURED_ANIMALS`, `FEATURED_PRODUCTS`, `MIDDLE_BANNERS`, `CATEGORY_PRODUCTS` |
| Product `sort` | `newest`, `price_asc`, `price_desc` |
| Animal `sort` | `newest`, `price_asc`, `price_desc`, `milk_desc` |

Treat these as open lists: show an unknown value as it is instead of failing.

---

## 11. App flow checklist

**Launch**
1. `GET /store` (keep it for the session) and `GET /home`.

**Browsing**
2. Product list: `GET /products` with filters; load more with `offset += limit` while `has_more` is `true`.
3. Product detail: `GET /products/{slug}`; the buyer picks a size (`variant_id`) and quantity.
4. Animals: `GET /animal-types`, then `GET /animal-types/{slug}/breeds` for the breed filter; `GET /animals`; `GET /animals/{slug}`.
5. Animal contact: Call `support_phone`, WhatsApp `whatsapp_number`, or `POST /animals/{slug}/enquiries`.

**Cart**
6. Store `{variant_id, quantity}` on the phone.
7. Open the cart screen → `POST /cart/quote`; replace the stored cart with the returned lines; show the totals,
   `below_minimum_by` and `free_delivery_gap`. Quote again after every quantity change.

**Checkout**
8. On opening checkout: make a new `checkout_token`, quote again, and keep the `total`.
9. Enable "Place order" only when `can_check_out` is `true`, `removed_count` is 0 and no line has `reduced_from`.
10. `POST /orders` with `expected_total` = that `total`.
    - `201` → show `order_ref`; save it with the phone number; clear the cart.
    - `422` → show `details` (field messages, or `form` at the top); quote again on a `form` error about the cart or prices.
    - `409` → quote again and show the new cart.
    - `503`, or a network error → resend the **same** request (same token).
    - `429` → wait `Retry-After` seconds.

**My orders**
11. For each saved reference: `POST /orders/track` with its phone number.

---

## 12. Endpoint summary

All paths start with `/api/v1/marketplace`.

| Method | Path | Body | Returns |
|--------|------|------|---------|
| GET | `/store` | — | Store settings |
| GET | `/home` | — | Store, trending links, banners, home blocks |
| GET | `/categories` | — | Top-level category list |
| GET | `/animal-types` | — | Animal type list |
| GET | `/animal-types/{slug}/breeds` | — | Breed list |
| GET | `/products` | query filters | Product cards, paged |
| POST | `/products/list` | JSON filters | Product cards, paged |
| GET | `/products/{slug}` | — | Product detail + related |
| GET | `/animals` | query filters | Animal cards, paged |
| POST | `/animals/list` | JSON filters | Animal cards, paged |
| GET | `/animals/{slug}` | — | Animal detail + similar |
| POST | `/animals/{slug}/enquiries` | Enquiry | `201` received (rate limited) |
| POST | `/cart/quote` | Cart items | Priced cart |
| POST | `/orders` | Order | `201` order reference (rate limited) |
| POST | `/orders/track` | Reference + phone | Order status and lines (rate limited) |

On a server running with `DEBUG=true` (development), the interactive schema of every endpoint is at `/docs`
(Swagger). Production servers do not show it.
