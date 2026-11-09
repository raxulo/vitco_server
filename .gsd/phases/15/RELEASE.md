# Marketplace Release Checklist (v1.2.0)

For whoever deploys this branch. Nothing here has been done on the server, and it can't be checked from the development workspace.

## Before deploying

- [ ] **Old mobile app.** Check whether any released app calls the old `/api/v1/marketplace` paths, such as `/banners`, `/trending-tags` or the order list. They no longer exist. Any app must move to [the new API](../../../docs/MARKETPLACE_API.md) first.
- [ ] **Legacy data.** Count the rows in `animals`, `product_offers` and `marketplace_orders` on the server. They stay in the database but no screen shows them, so check that nobody still needs open orders or listings from them.
- [ ] **Backup.** Back up the database. Startup creates the new `mkt_*` tables and starter data.
- [ ] **Branches.** `develop` and `main` are 35 commits behind this work line (DECISION-021). Decide how to bring them up to date.

## Server settings

- [ ] `MARKETPLACE_PUBLIC_URL`: the real `https://` address of the store. Without it, search engine links use whatever host the request names.
- [ ] `ENVIRONMENT=production` and `DEBUG=false`. Both default to development values.
- [ ] Leave `DATABASE_ECHO` off. With it on, buyer details and password hashes go to the logs.
- [ ] Keep one server process. With more, each one counts rate limits separately. Counts also reset on restart.
- [ ] **If a proxy is on another machine,** set Uvicorn's `--forwarded-allow-ips` to its address. Otherwise every customer counts as one IP and limits will block real buyers. A proxy on the same machine works as is.
- [ ] Serve the store over HTTPS. The login cookie has `secure=False` in code and should be changed once HTTPS is confirmed.

## Old logs

- [ ] **Clean up old log files on the server.** Versions before this branch wrote all SQL values to `logs/application.log*`, including password hashes. Delete them or restrict who can read them. This applies to any machine that ran the app.

## After deploying

- [ ] Don't copy a development database to the server with demo data in it. To clear it, run `python scripts/seed_marketplace_demo.py --remove`. Its phone numbers aren't real.
- [ ] Replace the starter data in the Control Center: store name, phone and WhatsApp numbers, delivery charge, policy pages.
- [ ] Add real listings and photos. Check that banner text is readable over the real photos, which the accessibility tool can't judge.
- [ ] Open `/robots.txt` and `/sitemap.xml` and confirm the links use the real address, then submit the sitemap to search engines.
- [ ] Place one test order end to end, then cancel it and confirm the stock returns.
- [ ] Measure page speed on the server. All figures so far are from a development machine.

## Decisions for the owner

| Question | Current state | Note |
|---|---|---|
| Drop the legacy tables? | Kept (DECISION-015) | Only after the checks above and a backup. Not done automatically |
| New order alerts? | None | A seller sees new orders only by opening the Control Center. Worth adding, because Cash on Delivery orders wait until someone looks |
| Admin REST API? | Not built (DECISION-023) | The Control Center is a website. Build when an app needs it |

## Known and accepted

- With 10 requests always in flight, home and product list pages are slightly over 300 ms on the development machine. See [VERIFICATION.md](VERIFICATION.md).
- `test_owner_options_super_admin` fails in the full suite, and also on `a345c6f`.
- Logs always go to the relative `logs/` folder, whatever `LOG_PATH` says.
