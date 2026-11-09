---
phase: 13
plan: 2
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 13.2 Summary: Store Pages & Enquiry Inbox

- Public pages: product and animal listings, details, search, policies, store 404.
- Animal page: Call, WhatsApp with a prefilled message, enquiry form with a hidden bot trap, and a fixed contact bar on phones.
- Phones and tablets show the photo, then price and contact, then details.
- Control Center: Enquiries tab with search, status filter, Call, WhatsApp, status and notes. The overview tile links to it.
- Bad query values are ignored instead of causing an error page.
- A test confirms every link on the home page opens.

## Test changes

Two older overview tests now restock first, because the low stock list shows only 8 rows and the test database is shared.
