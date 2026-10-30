"""Loader and parser for Bengaluru BBMP public toilet dataset.

OWNER: Ibrahim
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

DEFAULT_CSV_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "bbmp_toilets.csv"
FALLBACK_DOWNLOADS_CSV = Path(r"c:\Users\ISHAQ\Downloads\4e4a3896-2880-40dc-874d-01276dfb4f61.csv")


def _parse_bool(val: Any) -> bool | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return True
    if s in {"no", "n", "false", "0"}:
        return False
    return None


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s == "-":
        return None
    return s


def _parse_year(val: Any) -> int | None:
    s = _clean_str(val)
    if not s:
        return None
    match = re.search(r"\b(19\d\d|20\d\d)\b", s)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


class BBMPToiletRecord(BaseModel):
    id: str
    ward_no: str | None = None
    ward_name: str | None = None
    sub_division: str | None = None
    division: str | None = None
    zone: str | None = None
    location: str | None = None
    road_street: str | None = None
    year_of_construction: int | None = None
    has_gents: bool | None = None
    has_ladies: bool | None = None
    has_electricity: bool | None = None
    has_water: bool | None = None
    has_ugd: bool | None = None
    has_water_tank: bool | None = None
    has_bwssb: bool | None = None
    has_bore_well: bool | None = None
    contractor_name: str | None = None
    aee: str | None = None
    ae: str | None = None
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)

    @property
    def display_name(self) -> str:
        loc = self.location or ""
        road = self.road_street or ""
        ward = self.ward_name or (f"Ward {self.ward_no}" if self.ward_no else "")
        if loc and road and loc != road:
            return f"{loc}, {road}"
        if loc:
            return f"{loc} ({ward})" if ward else loc
        if road:
            return f"{road} ({ward})" if ward else road
        return f"BBMP Public Toilet - {ward}" if ward else "BBMP Public Toilet"


def load_bbmp_records(csv_path: Path | None = None) -> list[BBMPToiletRecord]:
    target_path = csv_path
    if target_path is None or not target_path.exists():
        if DEFAULT_CSV_PATH.exists():
            target_path = DEFAULT_CSV_PATH
        elif FALLBACK_DOWNLOADS_CSV.exists():
            target_path = FALLBACK_DOWNLOADS_CSV

    if target_path is None or not target_path.exists():
        return []

    records: list[BBMPToiletRecord] = []
    with open(target_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            lat_str = row.get("latitude") or row.get("Latitude")
            lon_str = row.get("longitude") or row.get("Longitude")
            if not lat_str or not lon_str:
                continue

            try:
                lat = float(str(lat_str).strip())
                lon = float(str(lon_str).strip())
            except (ValueError, TypeError):
                continue

            # Ensure coordinates are roughly within Karnataka / Bengaluru bounds
            if not (12.0 <= lat <= 14.5 and 76.5 <= lon <= 78.5):
                continue

            ward_no = _clean_str(row.get("Ward No"))
            rec_id = f"bbmp-w{ward_no or '0'}-{idx:03d}"

            record = BBMPToiletRecord(
                id=rec_id,
                ward_no=ward_no,
                ward_name=_clean_str(row.get("Ward Name")),
                sub_division=_clean_str(row.get("Sub_Division")),
                division=_clean_str(row.get("Division")),
                zone=_clean_str(row.get("Zone")),
                location=_clean_str(row.get("Location of the Toilet")),
                road_street=_clean_str(row.get("Name of the Road/ street")),
                year_of_construction=_parse_year(row.get("Year of construction")),
                has_gents=_parse_bool(row.get("Gents")),
                has_ladies=_parse_bool(row.get("Ladies")),
                has_electricity=_parse_bool(row.get("Electricity")),
                has_water=_parse_bool(row.get("Water")),
                has_ugd=_parse_bool(row.get("UGD")),
                has_water_tank=_parse_bool(row.get("Water Tank")),
                has_bwssb=_parse_bool(row.get("BWSSB")),
                has_bore_well=_parse_bool(row.get("Bore Well")),
                contractor_name=_clean_str(row.get("Contractor Name")),
                aee=_clean_str(row.get("AEE")),
                ae=_clean_str(row.get("AE")),
                latitude=lat,
                longitude=lon,
            )
            records.append(record)

    return records

