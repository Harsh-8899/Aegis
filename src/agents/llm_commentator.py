import os
import json
import time
import logging
import threading
import urllib.request
from typing import Dict, Any, Optional

logger = logging.getLogger("LLMCommentator")

class LLMCommentator:
    """
    Generates rich, context-aware market commentary and event explanations.
    Runs asynchronously in background threads to guarantee low latency in the live trading loop.
    Integrates with Google Gemini API if keys are available, otherwise falls back to a highly dynamic rule-based generator.
    """
    def __init__(self):
        self.latest_commentary: str = "Awaiting market stream synchronization..."
        self.last_update_time: float = 0.0
        self.lock = threading.Lock()
        
        # Check for Gemini credentials
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            logger.info("LLM Commentator initialized with Gemini API access.")
        else:
            logger.info("LLM Commentator initialized in local dynamic simulation mode.")

    def get_latest_commentary(self) -> str:
        """Thread-safe retrieval of latest commentary."""
        with self.lock:
            return self.latest_commentary

    def trigger_explanation(self, event_type: str, price: float, fusion_output: Dict[str, Any], 
                            model_outputs: Dict[str, Any], block_reason: str = ""):
        """
        Triggers commentary generation in a background thread to prevent blocking.
        """
        thread = threading.Thread(
            target=self._generate_explanation_worker,
            args=(event_type, price, fusion_output, model_outputs, block_reason),
            daemon=True,
            name="LLMCommentatorWorker"
        )
        thread.start()

    def _generate_explanation_worker(self, event_type: str, price: float, fusion_output: Dict[str, Any], 
                                     model_outputs: Dict[str, Any], block_reason: str):
        """Asynchronous execution task for text generation."""
        logger.info(f"Generating LLM commentary for event '{event_type}'...")
        start_t = time.time()
        
        # Compile contextual state description
        state_summary = {
            "event_type": event_type,
            "price": price,
            "signal": fusion_output.get("signal", "HOLD"),
            "regime": fusion_output.get("market_regime", "RANGING"),
            "confidence": fusion_output.get("confidence", 0.50),
            "trend_strength": fusion_output.get("trend_strength", "WEAK"),
            "risk_score": fusion_output.get("risk_score", 10.0),
            "volatility_state": fusion_output.get("volatility_state", "NORMAL"),
            "block_reason": block_reason,
            "models_status": {
                name: {
                    "regime": val.get("current_regime"),
                    "buy_prob": val.get("buy_prob"),
                    "sell_prob": val.get("sell_prob"),
                    "confidence": val.get("confidence")
                }
                for name, val in model_outputs.items()
            }
        }

        commentary = ""
        if self.api_key:
            commentary = self._call_gemini_api(state_summary)
            
        if not commentary:
            commentary = self._generate_simulated_commentary(state_summary)

        # Update cache
        with self.lock:
            self.latest_commentary = commentary
            self.last_update_time = time.time()
            
        elapsed = time.time() - start_t
        logger.info(f"LLM commentary generated in {elapsed:.2f}s.")

    def _call_gemini_api(self, state: Dict[str, Any]) -> Optional[str]:
        """Queries Google Gemini API with HTTP POST request."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        
        prompt = f"""
        You are Aegis-Gold AI, an institutional low-latency quant systems intelligence analyst.
        Explain the current Gold (XAU/USD) market state based on our mathematical models telemetry.
        
        Telemetry State (JSON):
        {json.dumps(state, indent=2)}
        
        Provide a concise, professional markdown explanation (max 150 words). Detail:
        1. What changed (Event: {state['event_type']}) and why the signal is {state['signal']}.
        2. Where the models agree or disagree (HMM, Kalman Filter, ML Ensembles, Z-Score).
        3. Critical risk warnings (Risk Score: {state['risk_score']}, Block Reason: {state['block_reason']}).
        4. Clear directional bias conclusions.
        Do not include greeting or preamble. Start directly with the analysis.
        """
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "maxOutputTokens": 300,
                "temperature": 0.3
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=8.0) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Gemini API request failed: {e}. Falling back to dynamic mock.")
            return None

    def _generate_simulated_commentary(self, state: Dict[str, Any]) -> str:
        """Generates a highly realistic, parameter-driven analyst explanation."""
        signal = state["signal"]
        event = state["event_type"]
        price = state["price"]
        regime = state["regime"]
        risk = state["risk_score"]
        block = state["block_reason"]
        
        # Build model consensus text
        consensus_elements = []
        for name, telemetry in state["models_status"].items():
            buy = telemetry["buy_prob"]
            sell = telemetry["sell_prob"]
            if buy > 0.6:
                consensus_elements.append(f"**{name}** flags Bullish (Prob: {buy:.2f})")
            elif sell > 0.6:
                consensus_elements.append(f"**{name}** flags Bearish (Prob: {sell:.2f})")

        consensus_text = ", ".join(consensus_elements) if consensus_elements else "Models in high-entropy noise state; no strong consensus."
        
        commentary = f"### [AEGIS INTEL] Gold Live Commentary — Event: {event.upper()}\n\n"
        commentary += f"**Market Summary:** XAU/USD is trading at **${price:.2f}** in a **{regime}** market state. "
        
        if signal == "BUY":
            commentary += f"The system has triggered a **BUY** signal with a confidence of **{state['confidence'] * 100:.1f}%**. "
            commentary += f"This decision is supported by the trend following consensus. "
        elif signal == "SELL":
            commentary += f"The system has triggered a **SELL** signal with a confidence of **{state['confidence'] * 100:.1f}%**. "
            commentary += f"This is driven by a strong bearish drift. "
        else:
            commentary += "The system is maintaining a **HOLD** posture. "
            if risk > 75.0:
                commentary += "Hold is enforced due to elevated volatility metrics and risk parameters. "
            else:
                commentary += "Hold is maintained due to lack of consensus. "

        commentary += f"\n\n**Model Alignment:** {consensus_text}\n\n"
        
        # Risk Gate summary
        if block:
            commentary += f"⚠️ **RISK EXPOSURE ALERT:** The Risk Gate has **BLOCKED** trade execution. "
            commentary += f"Reason: `{block}`. Volatility controls are actively restricting capital allocation."
        else:
            commentary += f"✅ **RISK GATE STATUS:** Passed. Risk score stands at `{risk}`. Open positions remain within safe bounds."

        return commentary
