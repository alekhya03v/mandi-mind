"""A deliberately small, traceable agent workflow."""
from __future__ import annotations
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from agent.llm import get_llm
from agent.tools import compare_nearby_markets, get_mandi_prices, get_price_trend, search_market_distances
from data.routing import estimate_market_distances

THRESHOLD_PERCENT = 5.0
DEFAULT_TRANSPORT_COST_PER_KM = 20.0

class MandiMindAgent:
    """Calls tools in a fixed order so the advice is easy to audit and explain."""
    def _call_tool(self, trace: list[dict[str, Any]], tool, arguments: dict[str, Any]) -> dict:
        result = tool.invoke(arguments)
        trace.append({"tool": tool.name, "input": arguments, "output": result})
        return result

    @staticmethod
    def _fallback_text(commodity, quantity, local, alternate, percent, extra, language):
        if language == "Hindi":
            if not local: return f"चयनित जिले में {commodity} की वर्तमान कीमत नहीं मिली।"
            if alternate and percent >= THRESHOLD_PERCENT: return f"{alternate['market']} में बेचने पर विचार करें। इसकी मॉडल कीमत स्थानीय कीमत से {percent:.1f}% अधिक है। {quantity:g} क्विंटल के लिए परिवहन और अन्य लागतों से पहले लगभग ₹{extra:,.0f} अधिक मिल सकते हैं।"
            return f"अभी स्थानीय बाजार में बेचें। वैकल्पिक बाजार की कीमत स्थानीय मॉडल कीमत से कम से कम {THRESHOLD_PERCENT:.0f}% अधिक नहीं है। परिवहन और अन्य लागतें शामिल नहीं हैं।"
        if language == "Marathi":
            if not local: return f"निवडलेल्या जिल्ह्यात {commodity} ची सध्याची किंमत सापडली नाही."
            if alternate and percent >= THRESHOLD_PERCENT: return f"{alternate['market']} येथे विक्री करण्याचा विचार करा. तेथील मॉडेल किंमत स्थानिक किमतीपेक्षा {percent:.1f}% जास्त आहे. {quantity:g} क्विंटलसाठी वाहतूक व इतर खर्चांपूर्वी अंदाजे ₹{extra:,.0f} अधिक मिळू शकतात."
            return f"सध्या स्थानिक बाजारात विक्री करा. पर्यायी बाजाराची किंमत स्थानिक मॉडेल किमतीपेक्षा किमान {THRESHOLD_PERCENT:.0f}% जास्त नाही. वाहतूक व इतर खर्च समाविष्ट नाहीत."
        if language == "Telugu":
            if not local: return f"ఎంచుకున్న జిల్లాలో {commodity} యొక్క ప్రస్తుత ధర దొరకలేదు."
            if alternate and percent >= THRESHOLD_PERCENT: return f"{alternate['market']}లో అమ్మడం పరిగణించండి. అక్కడి మోడల్ ధర స్థానిక ధర కంటే {percent:.1f}% ఎక్కువ. {quantity:g} క్వింటాళ్లకు రవాణా మరియు ఇతర ఖర్చులకు ముందు సుమారు ₹{extra:,.0f} ఎక్కువ రావచ్చు."
            return f"ప్రస్తుతానికి స్థానిక మార్కెట్‌లో అమ్మండి. ప్రత్యామ్నాయ మార్కెట్ ధర స్థానిక మోడల్ ధర కంటే కనీసం {THRESHOLD_PERCENT:.0f}% ఎక్కువ కాదు. రవాణా మరియు ఇతర ఖర్చులు ఇందులో లేవు."
        if language == "Tamil":
            if not local: return f"தேர்ந்தெடுக்கப்பட்ட மாவட்டத்தில் {commodity}க்கான தற்போதைய விலை கிடைக்கவில்லை."
            if alternate and percent >= THRESHOLD_PERCENT: return f"{alternate['market']} சந்தையில் விற்கலாம். அங்குள்ள மாடல் விலை உள்ளூர் விலையை விட {percent:.1f}% அதிகம். {quantity:g} குவிண்டால்களுக்கு போக்குவரத்து மற்றும் பிற செலவுகளுக்கு முன் சுமார் ₹{extra:,.0f} கூடுதலாக கிடைக்கலாம்."
            return f"தற்போதைக்கு உள்ளூர் சந்தையில் விற்கவும். மாற்றுச் சந்தை விலை உள்ளூர் மாடல் விலையை விட குறைந்தது {THRESHOLD_PERCENT:.0f}% அதிகமாக இல்லை. போக்குவரத்து மற்றும் பிற செலவுகள் சேர்க்கப்படவில்லை."
        if language == "Kannada":
            if not local: return f"ಆಯ್ಕೆ ಮಾಡಿದ ಜಿಲ್ಲೆಯಲ್ಲಿ {commodity}ಯ ಪ್ರಸ್ತುತ ಬೆಲೆ ಕಂಡುಬಂದಿಲ್ಲ."
            if alternate and percent >= THRESHOLD_PERCENT: return f"{alternate['market']}ಯಲ್ಲಿ ಮಾರಾಟ ಮಾಡುವುದನ್ನು ಪರಿಗಣಿಸಿ. ಅಲ್ಲಿನ ಮಾದರಿ ಬೆಲೆ ಸ್ಥಳೀಯ ಬೆಲೆಗಿಂತ {percent:.1f}% ಹೆಚ್ಚಾಗಿದೆ. {quantity:g} ಕ್ವಿಂಟಾಲ್‌ಗೆ ಸಾರಿಗೆ ಮತ್ತು ಇತರ ವೆಚ್ಚಗಳ ಮೊದಲು ಸುಮಾರು ₹{extra:,.0f} ಹೆಚ್ಚು ಸಿಗಬಹುದು."
            return f"ಸದ್ಯಕ್ಕೆ ಸ್ಥಳೀಯ ಮಾರುಕಟ್ಟೆಯಲ್ಲಿ ಮಾರಾಟ ಮಾಡಿ. ಪರ್ಯಾಯ ಮಾರುಕಟ್ಟೆಯ ಬೆಲೆ ಸ್ಥಳೀಯ ಮಾದರಿ ಬೆಲೆಗಿಂತ ಕನಿಷ್ಠ {THRESHOLD_PERCENT:.0f}% ಹೆಚ್ಚಿಲ್ಲ. ಸಾರಿಗೆ ಮತ್ತು ಇತರ ವೆಚ್ಚಗಳನ್ನು ಸೇರಿಸಲಾಗಿಲ್ಲ."
        if language == "Malayalam":
            if not local: return f"തിരഞ്ഞെടുത്ത ജില്ലയിൽ {commodity}യുടെ നിലവിലെ വില കണ്ടെത്താനായില്ല."
            if alternate and percent >= THRESHOLD_PERCENT: return f"{alternate['market']}യിൽ വിൽക്കുന്നത് പരിഗണിക്കുക. അവിടത്തെ മോഡൽ വില പ്രാദേശിക വിലയേക്കാൾ {percent:.1f}% കൂടുതലാണ്. {quantity:g} ക്വിന്റലിന് ഗതാഗതവും മറ്റ് ചെലവുകളും കണക്കാക്കുന്നതിന് മുമ്പ് ഏകദേശം ₹{extra:,.0f} കൂടുതൽ ലഭിക്കാം."
            return f"ഇപ്പോൾ പ്രാദേശിക വിപണിയിൽ വിൽക്കുക. ബദൽ വിപണി വില പ്രാദേശിക മോഡൽ വിലയേക്കാൾ കുറഞ്ഞത് {THRESHOLD_PERCENT:.0f}% കൂടുതലല്ല. ഗതാഗതവും മറ്റ് ചെലവുകളും ഉൾപ്പെടുത്തിയിട്ടില്ല."
        if not local:
            return f"I could not find a current {commodity} price for the selected district."
        if alternate and percent >= THRESHOLD_PERCENT:
            return (f"Consider selling in {alternate['market']}. Its modal price is ₹{alternate['modal_price']:,.0f} "
                    f"per quintal, about {percent:.1f}% above the local price of ₹{local['modal_price']:,.0f}. "
                    f"For {quantity:g} quintals, that is roughly ₹{extra:,.0f} more before transport, commission, and other costs.")
        return (f"Sell locally for now. The best alternate price is not at least {THRESHOLD_PERCENT:.0f}% higher "
                f"than the local modal price of ₹{local['modal_price']:,.0f} per quintal. This comparison does not include transport, commission, or other costs.")

    def advise(self, commodity: str, quantity: float, state: str, district: str, language: str = "English", transport_cost_per_quintal: float = 0.0, distance_km: float = 0.0, transport_cost_per_km: float = 0.0, market_distances_km: dict[str, float] | None = None, place: str = "", pincode: str = "", preferred_market: str = "") -> dict[str, Any]:
        trace = []
        local_result = self._call_tool(trace, get_mandi_prices,
            {"commodity": commodity, "state": state, "district": district})
        comparison = self._call_tool(trace, compare_nearby_markets,
            {"commodity": commodity, "state": state, "top_n": 100})
        local = None
        if preferred_market:
            local = next((row for row in local_result["markets"] if row["market"].casefold() == preferred_market.strip().casefold()), None)
        if local is None:
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
        routing = {"distances_km": market_distances_km or {}, "source": "manual or compatibility input", "note": None}
        if market_distances_km is None and not (place or pincode):
            routing = self._call_tool(trace, search_market_distances, {
                "origin": district,
                "state": state,
                "markets": ranked,
            })
        elif place or pincode:
            routing = estimate_market_distances(place, district, state, pincode, ranked)
        market_distances_km = routing["distances_km"]
        effective_transport_rate = max(0.0, transport_cost_per_km or DEFAULT_TRANSPORT_COST_PER_KM)
        market_profit_comparison = []
        for market in ranked:
            market_distance = max(0.0, float(market_distances_km.get(market["market"], distance_km)))
            market_transport = (
                quantity * max(0.0, transport_cost_per_quintal)
                if transport_cost_per_quintal > 0
                else market_distance * effective_transport_rate
            )
            gross_revenue = (market["modal_price"] or 0.0) * quantity
            market_profit_comparison.append({
                **market,
                "distance_km": market_distance,
                "gross_revenue": round(gross_revenue, 2),
                "transport_cost": round(market_transport, 2),
                "net_profit": round(gross_revenue - market_transport, 2),
            })
        best_profit_market = max(market_profit_comparison, key=lambda row: row["net_profit"], default=None)
        local_trend = self._call_tool(trace, get_price_trend,
            {"commodity": commodity, "state": state, "market": local["market"], "days": 7}) if local else None
        alternate_trend = self._call_tool(trace, get_price_trend,
            {"commodity": commodity, "state": state, "market": alternate["market"], "days": 7}) if alternate else None
        percent, extra = 0.0, 0.0
        transport_cost_total = 0.0
        if local and alternate and local["modal_price"]:
            percent = round(((alternate["modal_price"] - local["modal_price"]) / local["modal_price"]) * 100, 2)
            extra = max(0, alternate["modal_price"] - local["modal_price"]) * quantity
            if transport_cost_per_quintal > 0:
                transport_cost_total = quantity * transport_cost_per_quintal
            elif distance_km > 0 and transport_cost_per_km > 0:
                transport_cost_total = distance_km * transport_cost_per_km
        net_extra_revenue = max(0.0, extra - transport_cost_total)
        profit_alternate = best_profit_market if best_profit_market and (not local or best_profit_market["market"] != local["market"]) else None
        local_profit = next((row["net_profit"] for row in market_profit_comparison if local and row["market"] == local["market"]), 0.0)
        profit_extra = max(0.0, best_profit_market["net_profit"] - local_profit) if profit_alternate else extra
        recommendation = self._fallback_text(commodity, quantity, local, profit_alternate or alternate, percent, profit_extra, language)
        llm_used = False
        llm = get_llm()
        if llm and local:
            prompt = (f"Commodity: {commodity}. Quantity: {quantity} quintals. Local market: {local['market']} at "
                      f"₹{local['modal_price']}/quintal. Best alternate: {alternate['market'] if alternate else 'none'} "
                      f"at ₹{alternate['modal_price'] if alternate else 0}/quintal. Difference: {percent}%. "
                      f"The best market by net profit is {best_profit_market['market'] if best_profit_market else 'none'} at "
                      f"₹{best_profit_market['net_profit'] if best_profit_market else 0:,.0f} after transport. "
                      f"Distance: {distance_km} km. Transport cost: ₹{transport_cost_total:,.0f}. Net gain after transport: ₹{net_extra_revenue:,.0f}. "
                      f"Decision: {recommendation} Write two short practical sentences. Do not change the decision. "
                      f"Mention transport and commissions are not included. Write in {language}.")
            try:
                recommendation = str(llm.invoke([SystemMessage(content="You write clear, cautious mandi price advice."),
                    HumanMessage(content=prompt)]).content)
                llm_used = True
            except Exception:
                pass
        return {"recommendation": recommendation, "local_market": local, "best_market": alternate,
                "comparison_markets": ranked, "market_profit_comparison": market_profit_comparison,
                "best_profit_market": best_profit_market, "routing": routing,
                "transport_cost_per_km": effective_transport_rate,
                "local_trend": local_trend, "alternate_trend": alternate_trend,
                "percent_difference": percent, "estimated_extra_revenue": round(extra, 2),
                "distance_km": distance_km,
                "transport_cost_total": round(transport_cost_total, 2),
                "net_extra_revenue": round(net_extra_revenue, 2), "trace": trace,
                "source": local_result["source"], "source_note": local_result["note"] or comparison["note"],
                "llm_used": llm_used}
