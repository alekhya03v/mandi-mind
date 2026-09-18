from agent.agent import MandiMindAgent
from agent.tools import compare_nearby_markets, get_price_trend
from data.agmarknet_client import AgmarknetClient

def test_sample_filtering(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    rows, source, note = AgmarknetClient().fetch("Onion", "Maharashtra", "Nashik")
    assert len(rows) == 14
    assert source == "sample data" and note is None

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

def test_agent_creates_tool_trace(monkeypatch):
    monkeypatch.setenv("USE_SAMPLE_DATA", "true")
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = MandiMindAgent().advise("Onion", 50, "Maharashtra", "Nashik")
    names = [item["tool"] for item in result["trace"]]
    assert "get_mandi_prices" in names and "compare_nearby_markets" in names
    assert result["best_market"]["market"] == "Lasalgaon" and result["estimated_extra_revenue"] > 0
