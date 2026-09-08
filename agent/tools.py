"""The three data tools available to the MandiMind agent."""
from langchain_core.tools import tool
from data.agmarknet_client import AgmarknetClient, latest_by_market

@tool
def get_mandi_prices(commodity: str, state: str, district: str | None = None) -> dict:
    """Get newest min, max, modal price and arrivals for a commodity location."""
    rows, source, note = AgmarknetClient().fetch(commodity, state, district)
    return {"commodity": commodity, "state": state, "district": district,
            "markets": latest_by_market(rows), "source": source, "note": note}

@tool
def compare_nearby_markets(commodity: str, state: str, top_n: int = 5) -> dict:
    """Rank state markets by highest current modal price."""
    rows, source, note = AgmarknetClient().fetch(commodity, state)
    markets = [row for row in latest_by_market(rows) if row["modal_price"] is not None]
    markets.sort(key=lambda row: row["modal_price"], reverse=True)
    return {"commodity": commodity, "state": state, "markets": markets[:top_n],
            "source": source, "note": note}

@tool
def get_price_trend(commodity: str, market: str, days: int = 7) -> dict:
    """Describe recent modal-price movement for one commodity and market."""
    rows, source, note = AgmarknetClient().fetch(commodity, "Maharashtra", market=market)
    rows = sorted(rows, key=lambda row: row["arrival_date"])[-days:]
    prices = [row["modal_price"] for row in rows if row["modal_price"] is not None]
    change = round(((prices[-1] - prices[0]) / prices[0]) * 100, 2) if len(prices) > 1 and prices[0] else 0.0
    direction = "rising" if change > 1 else "falling" if change < -1 else "flat"
    return {"commodity": commodity, "market": market, "days": len(rows),
            "history": [{"date": row["arrival_date"], "modal_price": row["modal_price"]} for row in rows],
            "direction": direction, "percent_change": change, "source": source, "note": note}
