from agent.agent import MandiMindAgent
from agent.tools import compare_nearby_markets, get_price_trend, search_distance_between_places
from data.agmarknet_client import AgmarknetClient

def test_sample_filtering(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    rows, source, note = AgmarknetClient().fetch("Onion", "Maharashtra", "Nashik")
    assert len(rows) == 14
    assert source == "sample data" and note is None

def test_commodity_list_for_state(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    commodities = AgmarknetClient().commodities_for_state("Maharashtra")
    assert commodities == ["Onion", "Potato", "Tomato"]

def test_market_ranking(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    assert compare_nearby_markets.invoke({"commodity": "Onion", "state": "Maharashtra"})["markets"][0]["market"] == "Lasalgaon"

def test_trend_calculation(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    trend = get_price_trend.invoke({"commodity": "Onion", "state": "Maharashtra", "market": "Nashik", "days": 7})
    assert trend["direction"] == "rising" and trend["percent_change"] > 0

def test_api_failure_uses_sample_data(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "false")
    monkeypatch.delenv("DATA_GOV_API_KEY", raising=False)
    rows, source, note = AgmarknetClient().fetch("Onion", "Maharashtra")
    assert rows and source == "sample data fallback" and "unavailable" in note

def test_agent_accounts_for_transport_costs(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = MandiMindAgent().advise("Onion", 50, "Maharashtra", "Nashik", transport_cost_per_quintal=200)
    assert result["transport_cost_total"] == 10000
    assert result["net_extra_revenue"] < result["estimated_extra_revenue"]

def test_agent_compares_final_profit_by_market(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    result = MandiMindAgent().advise(
        "Onion", 50, "Maharashtra", "Nashik",
        transport_cost_per_km=20,
        market_distances_km={
            "Lasalgaon": 100,
            "Sangamner": 10,
            "Pune": 40,
            "Ahmednagar": 50,
            "Solapur": 60,
        },
    )
    rows = {row["market"]: row for row in result["market_profit_comparison"]}
    assert rows["Sangamner"]["transport_cost"] == 200
    assert rows["Lasalgaon"]["net_profit"] == rows["Lasalgaon"]["gross_revenue"] - rows["Lasalgaon"]["transport_cost"]
    assert result["best_profit_market"]["market"] == "Sangamner"

def test_agent_automatically_uses_location_routing(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    monkeypatch.setattr(
        "agent.agent.estimate_market_distances",
        lambda place, district, state, pincode, markets: {
            "distances_km": {market["market"]: 10 for market in markets},
            "source": "test routing",
            "note": None,
        },
    )
    result = MandiMindAgent().advise(
        "Onion", 50, "Maharashtra", "Nashik",
        place="Nashik", pincode="422001",
    )
    assert result["routing"]["source"] == "test routing"
    assert result["transport_cost_per_km"] == 20.0
    assert result["market_profit_comparison"][0]["transport_cost"] == 200


def test_agent_creates_tool_trace(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = MandiMindAgent().advise("Onion", 50, "Maharashtra", "Nashik")
    names = [item["tool"] for item in result["trace"]]
    assert "get_mandi_prices" in names and "compare_nearby_markets" in names
    assert result["best_market"]["market"] == "Lasalgaon" and result["estimated_extra_revenue"] > 0


def test_data_dropdowns_are_valid_for_live_records(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    client = AgmarknetClient()
    states = client.states()
    districts = client.districts_for_state("Maharashtra")
    commodities = client.commodities_for_state_and_district("Maharashtra", "Nashik")
    markets = client.markets_for_state_district_commodity("Maharashtra", "Nashik", "Onion")
    assert "Maharashtra" in states
    assert "Nashik" in districts
    assert "Onion" in commodities
    assert "Lasalgaon" in markets


def test_live_dropdown_uses_api_data_when_sample_mode_is_off(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "false")
    monkeypatch.setenv("DATA_GOV_API_KEY", "test-key")
    monkeypatch.setattr(
        "data.agmarknet_client.AgmarknetClient._live_rows",
        lambda self, state=None, district=None, commodity=None: [
            {"state": "Punjab", "district": "Ludhiana", "market": "Ludhiana", "commodity": "Wheat"},
            {"state": "Maharashtra", "district": "Nashik", "market": "Nashik", "commodity": "Onion"},
        ],
    )
    client = AgmarknetClient()
    assert "Punjab" in client.states()
    assert "Ludhiana" in client.districts_for_state("Punjab")
    assert "Wheat" in client.commodities_for_state_and_district("Punjab", "Ludhiana")
    assert "Ludhiana" in client.markets_for_state_district_commodity("Punjab", "Ludhiana", "Wheat")


def test_search_distance_between_places_uses_haversine_fallback(monkeypatch):
    monkeypatch.setattr("data.routing._geocode", lambda query: (78.0, 20.0) if "Nashik" in query else (78.5, 18.5))
    monkeypatch.setattr("data.routing._road_distance_km", lambda origin, destination: None)
    result = search_distance_between_places.invoke({"origin": "Nashik, Maharashtra", "destination": "Siddipet, Telangana"})
    assert result["distance_km"] > 0
    assert result["source"] in {"fallback_haversine", "estimated_distance"}
