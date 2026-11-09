# Marketplace API

The store API for the mobile app. It covers browsing, animal enquiries, guest Cash on Delivery orders and order tracking.

**Base path:** `/api/v1/marketplace`
**Login:** not needed. A logged-in user's token is optional on `POST /orders`, which links the order to that user.

## Rules for every call

- **Amounts are strings**, such as `"140.00"`, so paise stay exact. Don't parse them into floats for calculations.
- The server decides prices and totals. Show `total` from the server rather than adding it up on the phone.
- The app keeps the cart on the device and sends it to `POST /cart/quote` to get current prices and stock.

### Responses

A list:

```json
{
  "status": true, "code": 200, "message": "Products fetched successfully",
  "items": [],
  "limit": 24, "offset": 0, "total": 0, "pages": 1, "next_page": null, "has_more": false
}
```

A single record:

```json
{ "status": true, "code": 200, "message": "Store fetched successfully", "data": {} }
```

An error:

```json
{ "success": false, "error": { "code": "MARKETPLACE_TOO_MANY_REQUESTS", "message": "…", "details": {} } }
```

| Status | Meaning | What the app should do |
|---|---|---|
| 404 | The listing or order wasn't found | Show "not found" |
| 409 | The action isn't possible now, such as a sold animal or finished stock | Show `error.message`; for an order, quote the cart again |
| 422 | A value is invalid. For enquiries and orders, `error.details` maps a field name to its message; `form` means the whole request | Show the message beside the field |
| 429 | Too many attempts | Wait for the seconds in the `Retry-After` header |
| 503 | The server is busy and the order wasn't placed | Retry with the **same** `checkout_token` |

## Browsing

| Call | Returns |
|---|---|
| `GET /store` | Store name, contact details, delivery charge, minimum order, policies, and whether the store is open |
| `GET /home` | Store details, `trending_tags`, `hero_banners`, and `blocks` in the order set in the Control Center |
| `GET /categories` | Top-level categories |
| `GET /animal-types` | Animal types |
| `GET /animal-types/{slug}/breeds` | Breeds of one type |
| `GET /products` or `POST /products/list` | Product cards |
| `GET /products/{slug}` | `product` with sizes and images, plus `related` |
| `GET /animals` or `POST /animals/list` | Animal cards |
| `GET /animals/{slug}` | `animal` with full details, plus `similar` |

`GET` takes the filters as query values and `POST .../list` takes the same names as a JSON body.

**Products:** `search`, `category` (slug), `min_price`, `max_price`, `in_stock`, `sort` (`newest`, `price_asc`, `price_desc`), `limit` (1 to 100, default 24), `offset`.

**Animals:** `search`, `type` (slug), `breed` (id), `min_price`, `max_price`, `min_milk`, `lactation` (1 to 3, or 4 for fourth or later), `location`, `sort` (also `milk_desc`), `limit`, `offset`.

Each home block has a `section_type`, a `title`, and content in `categories`, `products`, `animals` or `banners`.

Animal `status` is `PUBLISHED` or `RESERVED` in lists. A detail page can also be `SOLD`, so an old link still opens; don't offer an enquiry for a sold animal.

## Animal enquiry

Animals are never added to a cart. The buyer asks, and the seller calls back.

`POST /animals/{slug}/enquiries`

```json
{ "buyer_name": "Asha Devi", "buyer_phone": "9876543210", "location": "Ramgarh", "message": "Is she still available?" }
```

Returns `201`. `location` and `message` are optional. Asking again about the same animal from the same number returns `201` without creating a second lead. A sold animal returns `409`.

## Cart and orders

### Price the cart

`POST /cart/quote`

```json
{ "items": [{ "variant_id": "…", "quantity": 2 }] }
```

`variant_id` comes from `sizes[].variant_id` on a product. Send up to 30 items, each with a quantity of up to 50.

| Field in `data` | Meaning |
|---|---|
| `lines` | Each line with its current price. `reduced_from` is set when stock cut the quantity |
| `removed_count` | Items dropped because they are no longer sold. Remove them from the device too |
| `subtotal`, `delivery_charge`, `total` | The amounts to show |
| `below_minimum_by` | How much more is needed to reach the minimum order |
| `can_check_out` | Whether the order can be placed |

### Place an order

`POST /orders`

```json
{
  "items": [{ "variant_id": "…", "quantity": 2 }],
  "buyer_name": "Asha Devi",
  "buyer_phone": "9876543210",
  "address_line": "12 Temple Road, Ramgarh",
  "city": "Jaipur",
  "state": "Rajasthan",
  "pincode": "302001",
  "notes": "Call before delivery",
  "checkout_token": "5f0c3a52-7c1b-4a55-9a3e-0d5f4d3f2a11",
  "expected_total": "240.00"
}
```

Returns `201` with `order_ref`, `total` and `status`. Save `order_ref` and show it to the buyer. Payment is Cash on Delivery.

- **`checkout_token`:** create one UUID when the checkout screen opens and keep it until the order succeeds. If the network drops, retry with the same token. The buyer gets the same order, not a second one.
- **`expected_total`:** send the `total` the buyer saw. If it has changed, the order is refused with `422` so the buyer can see the new amount. Quote the cart again before retrying.

### Track an order

`POST /orders/track`

```json
{ "order_ref": "VT-260911-ABC123", "phone": "9876543210" }
```

Returns the status, amounts and lines. The buyer's name and address are left out, because a reference and phone number are easily shared. A wrong reference and a wrong phone number both return the same `404`.

## Limits

Counted per IP address over 10 minutes, and shared with the website:

| Action | Attempts |
|---|---|
| Enquiries | 10 |
| Orders | 20 |
| Tracking | 20 |

## What isn't in this API

- Online payment and buyer accounts. Payment is Cash on Delivery only.
- Listing, changing or cancelling orders. Sellers do this in the Control Center.
- Managing listings. The Control Center has no REST API yet.
