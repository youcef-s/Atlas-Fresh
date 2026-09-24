"""Workbook loading and validation logic."""
from app.models import (
    FarmPlan,
    Client,
    StationConfig,
    ReferencePrices,
    LoadResponse,
    ValidationError,
    Segment,
    AcceptanceMode,
)
import openpyxl
from typing import cast


REQUIRED_FARM_COLUMNS = [
    "farm_id",
    "farm_name",
    "expected_daily_capacity_t",
    "expected_A_pct",
    "expected_B_pct",
    "expected_C_pct",
    "expected_D_pct",
    "actual_A_t",
    "actual_B_t",
    "actual_C_t",
    "actual_D_t",
]

REQUIRED_CLIENT_COLUMNS = [
    "client_id",
    "client_name",
    "acceptance_mode",
    "requested_segment",
    "demand_t",
    "export_price_per_t_eur",
]

REQUIRED_STATION_COLUMNS = [
    "station_id",
    "export_conditioning_capacity_t",
    "local_market_ratio",
]


def validate_multiple_of_5(value: float, field_name: str) -> str | None:
    if value < 0 or abs(value * 2 - round(value * 2)) > 0.001:
        return f"{field_name} must be non-negative multiple of 5"
    return None


def load_and_validate_workbook(file_path: str) -> LoadResponse:
    errors: list[ValidationError] = []
    wb = openpyxl.load_workbook(file_path, data_only=True)

    # --- Farms sheet ---
    farms: list[FarmPlan] = []
    if "Farms" not in wb.sheetnames:
        errors.append(ValidationError(sheet="Farms", identifier="", message="Missing 'Farms' sheet"))
    else:
        ws = wb["Farms"]
        headers = [cell.value for cell in next(ws.iter_rows(min_row=3, max_row=3, values_only=False))]
        header_map = {h: i for i, h in enumerate(headers) if h is not None}

        missing = [c for c in REQUIRED_FARM_COLUMNS if c not in header_map]
        if missing:
            errors.append(ValidationError(sheet="Farms", identifier="", message=f"Missing columns: {missing}"))
        else:
            seen_ids = set()
            for row_idx, row in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
                if not any(v is not None for v in row):
                    continue
                farm_id = str(row[header_map["farm_id"]]).strip()
                if not farm_id:
                    errors.append(ValidationError(sheet="Farms", identifier=f"row {row_idx}", message="Empty farm_id"))
                    continue
                if farm_id in seen_ids:
                    errors.append(ValidationError(sheet="Farms", identifier=farm_id, message="Duplicate farm_id"))
                    continue
                seen_ids.add(farm_id)

                try:
                    farm = FarmPlan(
                        farm_id=farm_id,
                        farm_name=str(row[header_map["farm_name"]]).strip(),
                        expected_daily_capacity_t=float(row[header_map["expected_daily_capacity_t"]]),
                        expected_A_pct=float(row[header_map["expected_A_pct"]]),
                        expected_B_pct=float(row[header_map["expected_B_pct"]]),
                        expected_C_pct=float(row[header_map["expected_C_pct"]]),
                        expected_D_pct=float(row[header_map["expected_D_pct"]]),
                        actual_A_t=float(row[header_map["actual_A_t"]]),
                        actual_B_t=float(row[header_map["actual_B_t"]]),
                        actual_C_t=float(row[header_map["actual_C_t"]]),
                        actual_D_t=float(row[header_map["actual_D_t"]]),
                    )
                    # Validate mix sums to 1.0
                    if abs(farm.expected_mix_sum - 1.0) > 0.001:
                        errors.append(ValidationError(
                            sheet="Farms", identifier=farm_id,
                            message=f"Expected mix percentages sum to {farm.expected_mix_sum:.3f}, must be 1.0"
                        ))
                    # Validate actuals are multiples of 5
                    for seg, attr in [(Segment.A, "actual_A_t"), (Segment.B, "actual_B_t"),
                                      (Segment.C, "actual_C_t"), (Segment.D, "actual_D_t")]:
                        err = validate_multiple_of_5(getattr(farm, attr), f"actual_{seg.value}_t")
                        if err:
                            errors.append(ValidationError(sheet="Farms", identifier=farm_id, message=err))
                    farms.append(farm)
                except Exception as e:
                    errors.append(ValidationError(sheet="Farms", identifier=farm_id, message=str(e)))

    # --- Clients sheet ---
    clients: list[Client] = []
    if "Clients" not in wb.sheetnames:
        errors.append(ValidationError(sheet="Clients", identifier="", message="Missing 'Clients' sheet"))
    else:
        ws = wb["Clients"]
        headers = [cell.value for cell in next(ws.iter_rows(min_row=3, max_row=3, values_only=False))]
        header_map = {h: i for i, h in enumerate(headers) if h is not None}

        missing = [c for c in REQUIRED_CLIENT_COLUMNS if c not in header_map]
        if missing:
            errors.append(ValidationError(sheet="Clients", identifier="", message=f"Missing columns: {missing}"))
        else:
            seen_ids = set()
            for row_idx, row in enumerate(ws.iter_rows(min_row=4, values_only=True), start=4):
                if not any(v is not None for v in row):
                    continue
                client_id = str(row[header_map["client_id"]]).strip()
                if not client_id:
                    errors.append(ValidationError(sheet="Clients", identifier=f"row {row_idx}", message="Empty client_id"))
                    continue
                if client_id in seen_ids:
                    errors.append(ValidationError(sheet="Clients", identifier=client_id, message="Duplicate client_id"))
                    continue
                seen_ids.add(client_id)

                try:
                    mode_str = str(row[header_map["acceptance_mode"]]).strip().upper()
                    if mode_str not in ("EXACT", "MINIMUM"):
                        raise ValueError(f"Invalid acceptance_mode: {mode_str}")
                    seg_str = str(row[header_map["requested_segment"]]).strip().upper()
                    if seg_str not in ("A", "B", "C", "D"):
                        raise ValueError(f"Invalid requested_segment: {seg_str}")

                    client = Client(
                        client_id=client_id,
                        client_name=str(row[header_map["client_name"]]).strip(),
                        acceptance_mode=AcceptanceMode(mode_str),
                        requested_segment=Segment(seg_str),
                        demand_t=float(row[header_map["demand_t"]]),
                        export_price_per_t_eur=float(row[header_map["export_price_per_t_eur"]]),
                    )
                    clients.append(client)
                except Exception as e:
                    errors.append(ValidationError(sheet="Clients", identifier=client_id, message=str(e)))

    # --- Station sheet ---
    station: StationConfig | None = None
    reference_prices: ReferencePrices | None = None
    if "Station" not in wb.sheetnames:
        errors.append(ValidationError(sheet="Station", identifier="", message="Missing 'Station' sheet"))
    else:
        ws = wb["Station"]
        # Station config at row 3
        headers = [cell.value for cell in next(ws.iter_rows(min_row=3, max_row=3, values_only=False))]
        header_map = {h: i for i, h in enumerate(headers) if h is not None}
        missing = [c for c in REQUIRED_STATION_COLUMNS if c not in header_map]
        if missing:
            errors.append(ValidationError(sheet="Station", identifier="", message=f"Missing columns: {missing}"))
        else:
            row = next(ws.iter_rows(min_row=4, max_row=4, values_only=True))
            try:
                station = StationConfig(
                    station_id=str(row[header_map["station_id"]]).strip(),
                    export_conditioning_capacity_t=float(row[header_map["export_conditioning_capacity_t"]]),
                    local_market_ratio=float(row[header_map["local_market_ratio"]]),
                )
                # Validate capacity multiple of 5
                err = validate_multiple_of_5(station.export_conditioning_capacity_t, "export_conditioning_capacity_t")
                if err:
                    errors.append(ValidationError(sheet="Station", identifier=station.station_id, message=err))
            except Exception as e:
                errors.append(ValidationError(sheet="Station", identifier="", message=str(e)))

        # Reference prices at row 12
        price_headers = [cell.value for cell in next(ws.iter_rows(min_row=12, max_row=12, values_only=False))]
        price_header_map = {h: i for i, h in enumerate(price_headers) if h is not None}
        if "segment" not in price_header_map or "reference_export_price_per_t_eur" not in price_header_map:
            errors.append(ValidationError(sheet="Station", identifier="", message="Missing reference price columns"))
        else:
            prices: dict[Segment, float] = {}
            for row in ws.iter_rows(min_row=13, values_only=True):
                if not any(v is not None for v in row):
                    continue
                seg_str = str(row[price_header_map["segment"]]).strip().upper()
                if seg_str not in ("A", "B", "C", "D"):
                    continue
                try:
                    prices[Segment(seg_str)] = float(row[price_header_map["reference_export_price_per_t_eur"]])
                except Exception as e:
                    errors.append(ValidationError(sheet="Station", identifier=seg_str, message=f"Invalid reference price: {e}"))
            if len(prices) != 4:
                errors.append(ValidationError(sheet="Station", identifier="", message="Missing reference prices for one or more segments"))
            else:
                reference_prices = ReferencePrices(prices=prices)

    if errors:
        return LoadResponse(success=False, errors=errors)

    return LoadResponse(
        success=True,
        farms=farms,
        clients=clients,
        station=station,
        reference_prices=reference_prices,
    )