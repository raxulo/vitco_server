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
5. **Open Marketplace**: Dairy cattle listings, cattle feed, and accessories accessible to both guest and authenticated users.

## Non-Goals (Out of Scope for Core Backend)
- Direct integration with proprietary proprietary hardware drivers in Python (handled at the client edge in Flutter / desktop).
- Raw video streaming (images and PDFs are supported via `MediaService`).

## Technical Constraints
- Asynchronous Python 3.13+ runtime with FastAPI.
- Naive IST timestamps (`app.core.clock`) for database compatibility.
- Clean Architecture / DDD separation across all modules.
- Strict Pydantic v2 schemas and response envelopes.

---
*Last updated: 2026-10-15*
