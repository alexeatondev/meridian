# 08 — Data Integration (plug-and-play providers)

**Version 0.1 · 2026-11-06**

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
