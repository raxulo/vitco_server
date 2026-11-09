# SPEC.md — Quickyee Project Specification

> **Status**: `FINALIZED`
>
> Dairy Management System & Real-Time Milk Collection Platform

## Vision
Quickyee is an ultra-fast, robust, and offline-capable dairy enterprise platform that bridges dairy farmers, village collection centers (VLCCs), bulk chilling centers (MCCs), and dairy processors. It enables instant milk weight and quality measurement (FAT/SNF), automated rate calculations, item advances, member ledgers, and seamless mobile synchronization.

## Goals
1. **Real-time Milk Collection**: High-speed, error-free morning and evening shift collections with hardware analyzer & weighing scale integration.
2. **Transparent Pricing & Rate Charts**: Precision milk valuation via configurable FAT/SNF slab matrices, formulas, and pro-rata pricing.
3. **Dispatch & Traceability**: Milk tanker dispatches from VLCC centers to MCC chilling plants with shift tracking and transit loss monitoring.
4. **Member Ledger & Supplies**: Cattle feed, store advances, loan recovery, and farmer ledger management.
5. **Open Marketplace (revamped in v1.2.0)**: A professional e-commerce store for guests and logged-in users. Animals (cow, buffalo, sheep, goat and more) are shown with price, lactation, milk litres per day, full description and images, and are bought through Call, WhatsApp or an enquiry. Products (milk, ghee, coconut and similar) follow mainstream e-commerce with categories, variants, stock, cart and Cash on Delivery guest checkout. Banners, trending and home sections are managed from a Super Admin Control Center. Super Admin is the only seller for now; the design allows Admin and Sub Admin sellers later. Details: [REQUIREMENTS.md](REQUIREMENTS.md).
6. **Bulk Data Exchange (v1.1.0)**: Farmers (per VLCC), VLCCs (per Admin / Sub Admin) and Prodata rate-chart rows can be exported to and imported from Excel through one job-based API used by the web panel and the mobile app. Imports upsert by code, discard only the bad rows with a reason, and report total / inserted / updated / discarded. Very large files are streamed so the server never crashes and no data is lost. Details: [REQUIREMENTS.md](REQUIREMENTS.md).

## Non-Goals (Out of Scope for Core Backend)
- Direct integration with proprietary proprietary hardware drivers in Python (handled at the client edge in Flutter / desktop).
- Raw video streaming (images and PDFs are supported via `MediaService`).
- Excel exchange for other entities (MCCs, collections, payments) and file formats other than `.xlsx` (CSV, `.xls`) — not in v1.1.0.
- Exporting passwords, database IDs (UUIDs) or profile images to Excel.
- Online payments, customer accounts / OTP login and a seller panel for Admin / Sub Admin — not in v1.2.0; the marketplace design leaves room for them.

## Technical Constraints
- Asynchronous Python 3.13+ runtime with FastAPI.
- Naive IST timestamps (`app.core.clock`) for database compatibility.
- Clean Architecture / DDD separation across all modules.
- Strict Pydantic v2 schemas and response envelopes.

---
*Last updated: 2026-11-08 (Goal 5 revised for milestone v1.2.0)*
