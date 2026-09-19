"""Tiny wrapper around the Agmarknet data.gov.in dataset."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any
import requests
from dotenv import load_dotenv

load_dotenv()
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
SAMPLE_PATH = Path(__file__).with_name("sample_data.json")

def _normalise(row: dict[str, Any]) -> dict[str, Any]:
    lower = {str(k).lower(): v for k, v in row.items()}
    def value(*names: str, default: Any = "") -> Any:
        return next((lower[n.lower()] for n in names if n.lower() in lower), default)
    def number(*names: str) -> float | None:
        raw = value(*names, default=None)
        try:
            return float(raw) if raw not in (None, "", "NA") else None
        except (TypeError, ValueError):
            return None
    return {"state": str(value("state")).strip(), "district": str(value("district")).strip(),
            "market": str(value("market")).strip(), "commodity": str(value("commodity")).strip(),
            "variety": str(value("variety")).strip(), "arrival_date": str(value("arrival_date")).strip(),
            "min_price": number("min_price"), "max_price": number("max_price"),
            "modal_price": number("modal_price"),
            "arrivals": number("arrivals", "arrival", "arrival_quantity")}

class AgmarknetClient:
    def __init__(self) -> None:
        self.use_sample_data = os.getenv("USE_SAMPLE_DATA", "true").lower() == "true"
        self.api_key = os.getenv("DATA_GOV_API_KEY", "")

    def _sample(self) -> list[dict[str, Any]]:
        with SAMPLE_PATH.open(encoding="utf-8") as file:
            return [_normalise(row) for row in json.load(file)]

    @staticmethod
    def _filter(rows, commodity, state, district=None, market=None):
        def match(actual, wanted):
            return not wanted or actual.casefold() == wanted.strip().casefold()
        return [row for row in rows if match(row["commodity"], commodity)
                and match(row["state"], state) and match(row["district"], district)
                and match(row["market"], market)]

    def states(self) -> list[str]:
        rows = self._sample() if self.use_sample_data else self._sample()
        return sorted({str(row["state"]).strip() for row in rows if str(row.get("state", "")).strip()})

    def districts_for_state(self, state: str) -> list[str]:
        rows = self._sample() if self.use_sample_data else self._sample()
        return sorted({str(row["district"]).strip() for row in rows if row.get("state", "").casefold() == state.strip().casefold() and row.get("district")})

    def commodities_for_state_and_district(self, state: str, district: str) -> list[str]:
        rows = self._sample() if self.use_sample_data else self._sample()
        return sorted({str(row["commodity"]).strip() for row in rows if row.get("state", "").casefold() == state.strip().casefold() and row.get("district", "").casefold() == district.strip().casefold() and row.get("commodity")})

    def markets_for_state_district_commodity(self, state: str, district: str, commodity: str) -> list[str]:
        rows = self._sample() if self.use_sample_data else self._sample()
        return sorted({str(row["market"]).strip() for row in rows if row.get("state", "").casefold() == state.strip().casefold() and row.get("district", "").casefold() == district.strip().casefold() and row.get("commodity", "").casefold() == commodity.strip().casefold() and row.get("market")})

    def _live(self, commodity, state, district=None):
        if not self.api_key:
            raise RuntimeError("DATA_GOV_API_KEY is not configured.")
        params = {"api-key": self.api_key, "format": "json", "limit": 100,
              "filters[state.keyword]": state.strip().title(),
              "filters[commodity]": commodity.strip().title()}
        if district:
            params["filters[district]"] = district.strip().title()
        response = requests.get(
            API_URL,
            params=params,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "MandiMind/1.0",
            },
            timeout=25,
        )
        response.raise_for_status()
        records = response.json().get("records", [])
        if not isinstance(records, list):
            raise RuntimeError("Agmarknet returned an unexpected response.")
        return [_normalise(row) for row in records]

    def fetch(self, commodity, state, district=None, market=None):
        if self.use_sample_data:
            return self._filter(self._sample(), commodity, state, district, market), "sample data", None
        try:
            rows = self._filter(self._live(commodity, state, district), commodity, state, district, market)
            return rows, "live Agmarknet data", None
        except (requests.RequestException, RuntimeError, ValueError) as error:
            rows = self._filter(self._sample(), commodity, state, district, market)
            return rows, "sample data fallback", f"Live API was unavailable, so sample data was used: {error}"

    def _live_commodities_for_state(self, state: str) -> list[str]:
        if not self.api_key:
            raise RuntimeError("DATA_GOV_API_KEY is not configured.")
        params = {"api-key": self.api_key, "format": "json", "limit": 200,
                  "filters[state.keyword]": state.strip().title()}
        response = requests.get(
            API_URL,
            params=params,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "MandiMind/1.0",
            },
            timeout=25,
        )
        response.raise_for_status()
        records = response.json().get("records", [])
        if not isinstance(records, list):
            raise RuntimeError("Agmarknet returned an unexpected response.")
        return sorted({str(row.get("commodity", "")).strip() for row in records if str(row.get("commodity", "")).strip()})

    def commodities_for_state(self, state: str) -> list[str]:
        if self.use_sample_data:
            rows = self._sample()
            commodities = sorted({
                str(row["commodity"]).strip()
                for row in rows
                if row.get("state", "").casefold() == state.strip().casefold() and row.get("commodity")
            })
            return commodities or ["Onion", "Potato", "Tomato"]
        try:
            return self._live_commodities_for_state(state) or ["Onion", "Potato", "Tomato"]
        except (requests.RequestException, RuntimeError, ValueError):
            rows = self._sample()
            commodities = sorted({
                str(row["commodity"]).strip()
                for row in rows
                if row.get("state", "").casefold() == state.strip().casefold() and row.get("commodity")
            })
            return commodities or ["Onion", "Potato", "Tomato"]

def latest_by_market(rows):
    latest = {}
    for row in sorted(rows, key=lambda item: item["arrival_date"], reverse=True):
        latest.setdefault(row["market"], row)
    return sorted(latest.values(), key=lambda item: item["market"])
