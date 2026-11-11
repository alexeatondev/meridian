"""Charles River order import file (MOCK FORMAT).

Charles River IMS loads orders from an import file today (an API connection comes later). Column names below
are a placeholder layout for development; map them to your firm's Charles River import specification with your
Charles River administrators before any real use. Every order carries its destination (route).
"""
from __future__ import annotations

CRD_COLUMNS = ["External Order ID", "Account", "Account Name", "Vehicle", "Security ID", "CUSIP", "Security Name",
               "Security Type", "Side", "Quantity", "Quantity Type", "Est. Price", "Est. Amount (USD)", "Order Type",
               "Destination", "Trade Date", "Manager", "Strategy", "Instructions", "Parent Order ID", "Tranche",
               "Meridian Trade List", "Meridian Record ID"]


def crd_rows(trade_list: dict, model) -> list[dict]:
    rows = []
    n = 0
    for f in trade_list["funds"]:
        fund = model.funds.get(f["fund_id"])
        for o in f["orders"]:
            n += 1
            inst = model.instruments.get(o["instrument"], {})
            fund_order = o["type"] in ("mutual_fund", "cit")
            parent = f"{trade_list['id']}-{n:04d}"
            parts = o.get("tranches") or [None]
            for t in parts:
                rows.append({
                    "External Order ID": f"{parent}-T{t['n']}" if t else parent,
                    "Account": fund.account if fund else f["fund_id"],
                    "Account Name": f"{fund.product_name} {fund.vintage}" if fund else f["fund_id"],
                    "Vehicle": fund.vehicle if fund else "",
                    "Security ID": o["instrument"], "CUSIP": inst.get("cusip", ""), "Security Name": o["name"],
                    "Security Type": o["type"], "Side": o["side"], "Quantity": t["quantity"] if t else o["quantity"],
                    "Quantity Type": o["quantity_type"], "Est. Price": o["price"],
                    "Est. Amount (USD)": t["est_amount"] if t else o["est_amount"],
                    "Order Type": "NAV" if fund_order else "MKT", "Destination": o["route"],
                    "Trade Date": t["date"] if t else trade_list["trade_date"],
                    "Manager": trade_list["created_by"]["name"], "Strategy": trade_list["strategy"],
                    "Instructions": ("Dollar-based fund order at NAV" if fund_order else "Exchange order")
                                    + "; run Charles River pre-trade compliance",
                    "Parent Order ID": parent if t else "", "Tranche": f"{t['n']} of {len(parts)}" if t else "",
                    "Meridian Trade List": trade_list["id"], "Meridian Record ID": trade_list.get("dr_ids", [""])[-1]})
    return rows
