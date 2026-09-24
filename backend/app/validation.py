"""Workbook loading and strict validation. Invalid input is reported, never repaired."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from app.models import (
    SEGMENTS,
    AcceptanceMode,
    Client,
    Farm,
    InputIssue,
    Segment,
    Snapshot,
    Station,
)

FARM_COLUMNS = [
    "farm_id",
    "farm_name",
    "expected_daily_capacity_t",
    *(f"expected_{s}_pct" for s in SEGMENTS),
    *(f"actual_{s}_t" for s in SEGMENTS),
]
CLIENT_COLUMNS = [
    "client_id",
    "client_name",
    "acceptance_mode",
    "requested_segment",
    "demand_t",
    "export_price_per_t_eur",
]
STATION_COLUMNS = ["station_id", "export_conditioning_capacity_t", "local_market_ratio"]
PRICE_COLUMNS = ["segment", "reference_export_price_per_t_eur"]

MIX_TOLERANCE = 1e-6


class WorkbookInvalid(Exception):
    def __init__(self, issues: list[InputIssue]) -> None:
        super().__init__(f"{len(issues)} input issue(s)")
        self.issues = issues


@dataclass
class _Collector:
    issues: list[InputIssue] = field(default_factory=list)

    def add(self, sheet: str, identifier: str, message: str, field_name: str | None = None) -> None:
        self.issues.append(
            InputIssue(sheet=sheet, identifier=identifier, field=field_name, message=message)
        )


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _is_multiple_of_5(value: float) -> bool:
    return abs(value / 5 - round(value / 5)) < 1e-9


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _table(
    ws: Worksheet, columns: list[str], issues: _Collector
) -> list[tuple[int, dict[str, Any]]] | None:
    """Find the header row whose first cell is columns[0]; return rows until the first blank."""
    rows = list(ws.iter_rows(values_only=True))
    for header_idx, row in enumerate(rows):
        if _text(row[0] if row else None) != columns[0]:
            continue
        header = {_text(v): i for i, v in enumerate(row) if _text(v)}
        missing = [c for c in columns if c not in header]
        if missing:
            issues.add(ws.title, "header", f"Missing column(s): {', '.join(missing)}")
            return None
        out: list[tuple[int, dict[str, Any]]] = []
        for offset, data in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            values = {c: data[header[c]] if header[c] < len(data) else None for c in columns}
            if all(v is None or _text(v) == "" for v in values.values()):
                break
            out.append((offset, values))
        return out
    issues.add(ws.title, "header", f"Header row starting with '{columns[0]}' not found")
    return None


def _number(
    issues: _Collector,
    sheet: str,
    ident: str,
    name: str,
    value: Any,
    *,
    multiple_of_5: bool = False,
    positive: bool = False,
    max_value: float | None = None,
) -> float | None:
    if not _is_number(value):
        issues.add(sheet, ident, f"{name} must be a number (got {value!r})", name)
        return None
    v = float(value)
    if v < 0:
        issues.add(sheet, ident, f"{name} must not be negative (got {v:g})", name)
        return None
    if positive and v == 0:
        issues.add(sheet, ident, f"{name} must be greater than 0", name)
        return None
    if max_value is not None and v > max_value:
        issues.add(sheet, ident, f"{name} must be between 0 and {max_value:g} (got {v:g})", name)
        return None
    if multiple_of_5 and not _is_multiple_of_5(v):
        issues.add(sheet, ident, f"{name} must be a multiple of 5 t (got {v:g})", name)
        return None
    return v


def _id(
    issues: _Collector, sheet: str, row: int, value: Any, seen: set[str], label: str
) -> str | None:
    ident = _text(value)
    if not ident:
        issues.add(sheet, f"row {row}", f"Missing {label}", label)
        return None
    if ident in seen:
        issues.add(sheet, ident, f"Duplicate {label} '{ident}' (row {row})", label)
        return None
    seen.add(ident)
    return ident


def _parse_farms(ws: Worksheet, issues: _Collector) -> list[Farm]:
    farms: list[Farm] = []
    seen: set[str] = set()
    for row, v in _table(ws, FARM_COLUMNS, issues) or []:
        fid = _id(issues, ws.title, row, v["farm_id"], seen, "farm_id")
        if fid is None:
            continue
        before = len(issues.issues)
        cap = _number(
            issues, ws.title, fid, "expected_daily_capacity_t", v["expected_daily_capacity_t"]
        )
        if cap is not None and abs(cap * 10 - round(cap * 10)) > 1e-9:
            issues.add(
                ws.title,
                fid,
                "expected_daily_capacity_t allows at most one decimal",
                "expected_daily_capacity_t",
            )
        mix: dict[Segment, float] = {}
        actual: dict[Segment, int] = {}
        for s in SEGMENTS:
            pct = _number(
                issues, ws.title, fid, f"expected_{s}_pct", v[f"expected_{s}_pct"], max_value=1
            )
            if pct is not None:
                mix[s] = pct
            t = _number(
                issues, ws.title, fid, f"actual_{s}_t", v[f"actual_{s}_t"], multiple_of_5=True
            )
            if t is not None:
                actual[s] = round(t)
        if len(mix) == 4 and abs(sum(mix.values()) - 1) > MIX_TOLERANCE:
            issues.add(
                ws.title,
                fid,
                f"Expected mix must total 1.0 (got {sum(mix.values()):.3f})",
                "expected_mix",
            )
        if len(issues.issues) == before and cap is not None:
            farms.append(
                Farm(
                    farm_id=fid,
                    farm_name=_text(v["farm_name"]) or fid,
                    expected_capacity_t=cap,
                    expected_mix=mix,
                    actual_t=actual,
                )
            )
    if not farms and not issues.issues:
        issues.add(ws.title, "sheet", "No farm rows found")
    return farms


def _parse_clients(ws: Worksheet, issues: _Collector) -> list[Client]:
    clients: list[Client] = []
    seen: set[str] = set()
    for row, v in _table(ws, CLIENT_COLUMNS, issues) or []:
        cid = _id(issues, ws.title, row, v["client_id"], seen, "client_id")
        if cid is None:
            continue
        before = len(issues.issues)
        mode = _text(v["acceptance_mode"])
        if mode not in AcceptanceMode.__members__:
            issues.add(
                ws.title,
                cid,
                f"acceptance_mode must be EXACT or MINIMUM (got '{mode}')",
                "acceptance_mode",
            )
        seg = _text(v["requested_segment"])
        if seg not in Segment.__members__:
            issues.add(
                ws.title,
                cid,
                f"requested_segment must be A, B, C or D (got '{seg}')",
                "requested_segment",
            )
        demand = _number(issues, ws.title, cid, "demand_t", v["demand_t"], multiple_of_5=True)
        price = _number(
            issues,
            ws.title,
            cid,
            "export_price_per_t_eur",
            v["export_price_per_t_eur"],
            positive=True,
        )
        if len(issues.issues) == before and demand is not None and price is not None:
            clients.append(
                Client(
                    client_id=cid,
                    client_name=_text(v["client_name"]) or cid,
                    acceptance_mode=AcceptanceMode(mode),
                    requested_segment=Segment(seg),
                    demand_t=round(demand),
                    price_per_t_eur=price,
                )
            )
    if not clients and not issues.issues:
        issues.add(ws.title, "sheet", "No client rows found")
    return clients


def _parse_station(ws: Worksheet, issues: _Collector) -> Station | None:
    before = len(issues.issues)
    rows = _table(ws, STATION_COLUMNS, issues) or []
    if len(rows) != 1:
        if not issues.issues[before:]:
            issues.add(
                ws.title, "station", f"Exactly one station row is required (found {len(rows)})"
            )
        return None
    _, v = rows[0]
    sid = _text(v["station_id"])
    if not sid:
        issues.add(ws.title, "station", "Missing station_id", "station_id")
    cap = _number(
        issues,
        ws.title,
        sid or "station",
        "export_conditioning_capacity_t",
        v["export_conditioning_capacity_t"],
        multiple_of_5=True,
        positive=True,
    )
    ratio = _number(
        issues,
        ws.title,
        sid or "station",
        "local_market_ratio",
        v["local_market_ratio"],
        max_value=1,
    )

    prices: dict[Segment, float] = {}
    for row, p in _table(ws, PRICE_COLUMNS, issues) or []:
        seg = _text(p["segment"])
        if seg not in Segment.__members__:
            issues.add(
                ws.title, f"row {row}", f"Unknown reference-price segment '{seg}'", "segment"
            )
            continue
        if Segment(seg) in prices:
            issues.add(ws.title, seg, f"Duplicate reference price for segment {seg}", "segment")
            continue
        price = _number(
            issues,
            ws.title,
            seg,
            "reference_export_price_per_t_eur",
            p["reference_export_price_per_t_eur"],
            positive=True,
        )
        if price is not None:
            prices[Segment(seg)] = price
    for s in SEGMENTS:
        if s not in prices and not any(i.identifier == s for i in issues.issues):
            issues.add(ws.title, s, f"Missing reference export price for segment {s}", "segment")

    if len(issues.issues) > before or cap is None or ratio is None:
        return None
    return Station(
        station_id=sid,
        capacity_t=round(cap),
        local_market_ratio=ratio,
        reference_price_per_t_eur=prices,
    )


def load_snapshot(source: Path) -> Snapshot:
    """Read the workbook read-only and return a validated snapshot or raise WorkbookInvalid."""
    issues = _Collector()
    try:
        wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    except FileNotFoundError:
        issues.add("Workbook", str(source.name), "Workbook file not found on the server")
        raise WorkbookInvalid(issues.issues) from None
    except Exception as exc:  # corrupt or non-xlsx file
        issues.add("Workbook", str(source.name), f"Workbook could not be read: {exc}")
        raise WorkbookInvalid(issues.issues) from exc

    try:
        sheets = {}
        for name in ("Farms", "Clients", "Station"):
            if name in wb.sheetnames:
                sheets[name] = wb[name]
            else:
                issues.add(name, "sheet", f"Sheet '{name}' is missing")
        farms = _parse_farms(sheets["Farms"], issues) if "Farms" in sheets else []
        clients = _parse_clients(sheets["Clients"], issues) if "Clients" in sheets else []
        station = _parse_station(sheets["Station"], issues) if "Station" in sheets else None
    finally:
        wb.close()

    if issues.issues or station is None:
        raise WorkbookInvalid(issues.issues)
    return Snapshot(farms=farms, clients=clients, station=station)
