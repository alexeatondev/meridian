# 09 — Data Integration (plug-and-play providers)

**Version 0.3 · 2026-11-10**

## Current setup: free public data
| Source | Provides | Notes |
|---|---|---|
| `yahoo` (Yahoo Finance) | Monthly total returns for the 12 proxy funds, spliced with older index funds back to 1990s | Unofficial, personal/non-commercial terms. Replace before production |
| `fred` (St. Louis Fed) | Macro indicators, credit spreads, bond yields, T-bill returns for cash | Set `FRED_API_KEY` (free) — the keyless download times out from cloud runners. Some series (ICE BofA) are copyrighted |
| `treasury` (US Treasury) | Par yield curve → cash, 5/10/30-year yields, 10y−2y slope | Public domain |
| `manual` | Cited hand-maintained values (e.g. US CAPE 41.07, Oct 2026, Multpl/Shiller) | `config/manual_inputs.yaml` |
| `cache` | Point-in-time copy written by `meridian data refresh` | Refreshed monthly by the `data-refresh` workflow; git history = point-in-time record |
| `synthetic` | Fallback only, for assets or fields nobody else covered | Always flagged by dataset and asset on every memo, report and Console page |

## Plug in / unplug / combine
```bash
meridian data list                       # sources, datasets, routing (unplugged shown in parentheses)
meridian data enable bloomberg_snowflake # plug in
meridian data disable yahoo              # unplug
meridian data route returns.monthly bloomberg_snowflake yahoo cache --mode merge --fallback synthetic
meridian data test treasury              # try one source live
meridian data refresh                    # fetch live sources into data/cache
```
**Merge mode** combines several sources for the same dataset. The earlier source wins per key. Time series fill gaps in *time*, so one vendor can cover recent years and another older history. Snapshots fill gaps per *field*, so a valuation can take CAPE from one source and dividend yield from another. Every row records its source (`_source`). The **fallback** tier only covers assets or fields nobody else supplied, and never patches holes inside a real return history.

New free sources need no code when they are a CSV URL (`provider: csv_url`).

## Design
Agents and analytics only ever see **canonical datasets**. Behind them, any number of **sources** can serve each dataset. A source is a *provider* (who owns the data) plus a *transport* (how Meridian reaches it).

```
          ┌──────────── canonical datasets ────────────┐
agents →  returns.monthly · macro.indicators · fundamentals.valuation · credit.ratings · yields.current
          └──────────────────────┬─────────────────────┘
                     routing (priority + fallback)
     ┌───────────────┬───────────┴────────┬──────────────┬───────────┐
 Bloomberg        FactSet             S&P Global       Moody's      Fitch     … any vendor
  direct │ snowflake  direct │ snowflake   direct │ snowflake  direct │ snowflake
```

| Transport | Use when | Adapter |
|---|---|---|
| `direct` | You license the vendor's API/SDK (Bloomberg BLPAPI/B-PIPE, FactSet APIs, S&P/Moody's/Fitch feeds) | `BloombergSource`, `FactSetSource`, `RestSource` |
| `snowflake` | Vendor data arrives in Snowflake (Marketplace share or your own data product) | `SnowflakeSource`: one adapter for every provider; SQL + key mapping live in config |
| `file` | Parquet/CSV drops | `FileSource` |
| `generated` | Pilot/testing | `SyntheticSource`: every output is labeled SYNTHETIC in the ledger, memo and compliance report |

## How to plug a provider in
1. In `config/data_sources.yaml`, set the source's `enabled: true`. For Snowflake, edit the `sql` to match your tables. Columns must be aliased to the canonical names.
2. Map identifiers in `config/universe.yaml` (`bloomberg`, `factset`, `snowflake_key`, …).
3. Set credentials as **environment variables / secrets** (names are in the config; values never go in git).
4. Reorder `routing` to set priority. Failed or unconfigured sources fall through to the next source, and every attempt is recorded in the run's data-snapshot decision record.
5. Mark `license_review` for the provider once the vendor confirms AI/LLM use is permitted under your contract.
6. Check with `meridian data`.

## How to unplug
Set `enabled: false` or remove it from `routing`. No code changes.

## Snapshots and lineage
Each run writes the exact data it used to `runs/<run_id>/snapshot/`, with SHA-256 hashes and a snapshot ID that every downstream decision record references.

## Status of adapters (v0.1)
| Adapter | Status |
|---|---|
| Synthetic, File, Snowflake | Implemented. Snowflake uses key-pair auth via `snowflake-connector-python` |
| Bloomberg direct | Implemented against BLPAPI HistoricalDataRequest. Needs a Terminal/B-PIPE session to test |
| FactSet direct | Implemented against the Prices API. Confirm endpoint/fields for your subscription |
| S&P / Moody's / Fitch direct | Generic REST adapter. Endpoint and field mapping are configured per contract. **Snowflake delivery is the recommended path** |

## Cashflows and positions for trading (2026-11-10)
| Data | Source today | Planned |
|---|---|---|
| Daily cashflows | Excel/CSV upload, hand entry, or the API (`POST /api/trading/cashflows` with the ingest token) | Transfer-agent files (SS&C for mutual funds) and custodian files (State Street for CITs), by file drop or API |
| Positions and cash at last close | Example positions generated from the glide path (`config/trading.yaml`) | Custodian and TA position files, or Charles River if it is the official book of positions (open question, doc 17 §9) |
| Prices | Example prices in `config/trading.yaml` | Vendor or custodian prices |
| Security master | `config/trading.yaml` (funds, ETFs, a T-bill, candidates) | Vendor or Charles River security master; fixes issuer naming (F-4) |
| Orders out | Charles River import file (mock layout) | Charles River API; results and fills back |
