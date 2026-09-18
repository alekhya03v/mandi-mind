"""A deliberately small, traceable agent workflow."""
from __future__ import annotations
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from agent.llm import get_llm
from agent.tools import compare_nearby_markets, get_mandi_prices, get_price_trend

THRESHOLD_PERCENT = 5.0

class MandiMindAgent:
    """Calls tools in a fixed order so the advice is easy to audit and explain."""
    def _call_tool(self, trace: list[dict[str, Any]], tool, arguments: dict[str, Any]) -> dict:
        result = tool.invoke(arguments)
        trace.append({"tool": tool.name, "input": arguments, "output": result})
        return result

    @staticmethod
    def _fallback_text(commodity, quantity, local, alternate, percent, extra):
        if not local:
            return f"I could not find a current {commodity} price for the selected district."
        if alternate and percent >= THRESHOLD_PERCENT:
            return (f"Consider selling in {alternate['market']}. Its modal price is ₹{alternate['modal_price']:,.0f} "
                    f"per quintal, about {percent:.1f}% above the local price of ₹{local['modal_price']:,.0f}. "
                    f"For {quantity:g} quintals, that is roughly ₹{extra:,.0f} more before transport, commission, and other costs.")
        return (f"Sell locally for now. The best alternate price is not at least {THRESHOLD_PERCENT:.0f}% higher "
                f"than the local modal price of ₹{local['modal_price']:,.0f} per quintal. This comparison does not include transport, commission, or other costs.")

    def advise(self, commodity: str, quantity: float, state: str, district: str) -> dict[str, Any]:
        trace = []
        local_result = self._call_tool(trace, get_mandi_prices,
            {"commodity": commodity, "state": state, "district": district})
        comparison = self._call_tool(trace, compare_nearby_markets,
            {"commodity": commodity, "state": state, "top_n": 5})
        # A district can contain more than one mandi. For this simple PoC, prefer
        # the market whose name matches the district, such as Nashik mandi in Nashik.
        local = next(
            (
                row
                for row in local_result["markets"]
                if row["market"].casefold() == district.strip().casefold()
            ),
            next(iter(local_result["markets"]), None),
        )
        ranked = comparison["markets"]
        alternate = next((row for row in ranked if not local or row["market"] != local["market"]), None)
        local_trend = self._call_tool(trace, get_price_trend,
            {"commodity": commodity, "state": state, "market": local["market"], "days": 7}) if local else None
        alternate_trend = self._call_tool(trace, get_price_trend,
            {"commodity": commodity, "state": state, "market": alternate["market"], "days": 7}) if alternate else None
        percent, extra = 0.0, 0.0
        if local and alternate and local["modal_price"]:
            percent = round(((alternate["modal_price"] - local["modal_price"]) / local["modal_price"]) * 100, 2)
            extra = max(0, alternate["modal_price"] - local["modal_price"]) * quantity
        recommendation = self._fallback_text(commodity, quantity, local, alternate, percent, extra)
        llm_used = False
        llm = get_llm()
        if llm and local:
            prompt = (f"Commodity: {commodity}. Quantity: {quantity} quintals. Local market: {local['market']} at "
                      f"₹{local['modal_price']}/quintal. Best alternate: {alternate['market'] if alternate else 'none'} "
                      f"at ₹{alternate['modal_price'] if alternate else 0}/quintal. Difference: {percent}%. "
                      f"Decision: {recommendation} Write two short practical sentences. Do not change the decision. "
                      "Mention that transport and commissions are not included.")
            try:
                recommendation = str(llm.invoke([SystemMessage(content="You write clear, cautious mandi price advice."),
                    HumanMessage(content=prompt)]).content)
                llm_used = True
            except Exception:
                pass
        return {"recommendation": recommendation, "local_market": local, "best_market": alternate,
                "comparison_markets": ranked, "local_trend": local_trend, "alternate_trend": alternate_trend,
                "percent_difference": percent, "estimated_extra_revenue": round(extra, 2), "trace": trace,
                "source": local_result["source"], "source_note": local_result["note"] or comparison["note"],
                "llm_used": llm_used}
