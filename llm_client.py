"""
llm_client.py — Pluggable LLM backend for the pre-vis pipeline.

Supported backends:
  groq      (free)   GROQ_API_KEY       → openai/gpt-oss-120b
  anthropic (paid)   ANTHROPIC_API_KEY  → claude-opus-4-5
  gemini    (paid)   GEMINI_API_KEY     → gemini-2.0-flash
  openai    (paid)   OPENAI_API_KEY     → gpt-4o

Selection (first match wins):
  1. --backend flag passed to pipeline.py / screenplay_to_scene.py
  2. LLM_BACKEND env var  (e.g. export LLM_BACKEND=anthropic)
  3. Auto-detect: whichever API key is found first (Groq → Anthropic → Gemini → OpenAI)

Override the model for any backend:
  export ANTHROPIC_MODEL=claude-opus-4-5
  export GEMINI_MODEL=gemini-2.5-pro
  export GROQ_MODEL=openai/gpt-oss-120b
  export OPENAI_MODEL=gpt-4o

Installation (only install what you need):
  pip install requests                    # Groq (already used)
  pip install anthropic                   # Claude
  pip install google-generativeai         # Gemini
  pip install openai                      # OpenAI / any OpenAI-compatible API
"""

import os
import sys

# ── Backend registry ──────────────────────────────────────────────────────────

BACKENDS = {
    "groq": {
        "env":           "GROQ_API_KEY",
        "default_model": "openai/gpt-oss-120b",
        "label":         "Groq (free) — gpt-oss-120b",
        "model_env":     "GROQ_MODEL",
        "install":       "pip install requests",
    },
    "anthropic": {
        "env":           "ANTHROPIC_API_KEY",
        "default_model": "claude-opus-4-5",
        "label":         "Anthropic — Claude",
        "model_env":     "ANTHROPIC_MODEL",
        "install":       "pip install anthropic",
    },
    "gemini": {
        "env":           "GEMINI_API_KEY",
        "default_model": "gemini-2.0-flash",
        "label":         "Google — Gemini",
        "model_env":     "GEMINI_MODEL",
        "install":       "pip install google-generativeai",
    },
    "openai": {
        "env":           "OPENAI_API_KEY",
        "default_model": "gpt-4o",
        "label":         "OpenAI — GPT",
        "model_env":     "OPENAI_MODEL",
        "install":       "pip install openai",
    },
}

AUTO_ORDER = ["groq", "anthropic", "gemini", "openai"]


class LLMClient:
    def __init__(self, backend: str = "auto", model: str = None):
        """
        backend: "auto" | "groq" | "anthropic" | "gemini" | "openai"
        model:   optional model name override (e.g. "gemini-2.5-pro")
        """
        self.backend = self._resolve_backend(backend)
        cfg          = BACKENDS[self.backend]
        self.model   = model or os.environ.get(cfg["model_env"], cfg["default_model"])
        self.api_key = os.environ.get(cfg["env"], "")
        print(f"  🤖 Backend : {cfg['label']}")
        print(f"  🧠 Model   : {self.model}")

    # ── Backend selection ─────────────────────────────────────────────────────

    def _resolve_backend(self, requested: str) -> str:
        if requested == "auto":
            # Check env var first
            env_b = os.environ.get("LLM_BACKEND", "").lower()
            if env_b in BACKENDS:
                requested = env_b
            else:
                # Auto-detect from available keys
                for b in AUTO_ORDER:
                    if os.environ.get(BACKENDS[b]["env"]):
                        return b
                self._no_key_error()

        if requested not in BACKENDS:
            print(f"❌ Unknown backend '{requested}'. Choose from: {', '.join(BACKENDS)}")
            sys.exit(1)

        if not os.environ.get(BACKENDS[requested]["env"]):
            cfg = BACKENDS[requested]
            print(f"\n❌ {cfg['env']} is not set.")
            print(f"   Get a key for {cfg['label']} and run:")
            print(f"   export {cfg['env']}=your_key_here")
            print(f"\n   Also make sure the SDK is installed:")
            print(f"   {cfg['install']}")
            sys.exit(1)

        return requested

    def _no_key_error(self):
        print("\n❌ No LLM API key found. Set one of:")
        for b, cfg in BACKENDS.items():
            print(f"   export {cfg['env']}=your_key   # {cfg['label']}")
        print("\n   Then re-run. Or use --backend groq and get a free key at https://console.groq.com")
        sys.exit(1)

    # ── Unified call ──────────────────────────────────────────────────────────

    def call(self, prompt: str, max_tokens: int = 4096) -> str:
        dispatch = {
            "groq":      self._call_groq,
            "anthropic": self._call_anthropic,
            "gemini":    self._call_gemini,
            "openai":    self._call_openai,
        }
        return dispatch[self.backend](prompt, max_tokens)

    # ── Groq ──────────────────────────────────────────────────────────────────

    def _call_groq(self, prompt: str, max_tokens: int) -> str:
        import time
        import requests
        # Free tier has a low tokens-per-minute cap, so Phase 1 + Phase 2 back-to-back
        # usually trips a 429 — wait out the window Groq asks for, then retry.
        body = {
            "model":       self.model,
            "messages":    [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens":  max_tokens,
        }
        # gpt-oss reasoning tokens count against max_tokens; at the default effort they can
        # use up the whole budget and cut the JSON off. Low effort leaves room for the answer.
        if "gpt-oss" in self.model:
            body["reasoning_effort"] = os.environ.get("GROQ_REASONING_EFFORT", "low")
        for attempt in range(4):
            resp = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type":  "application/json",
                },
                json=body,
                timeout=120,
            )
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            if resp.status_code == 429 and attempt < 3:
                wait = min(float(resp.headers.get("retry-after", 20)) + 1, 65)
                print(f"  ⏳ Groq rate limit — waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            break
        raise RuntimeError(f"Groq error {resp.status_code}: {resp.text[:400]}")

    # ── Anthropic (Claude) ────────────────────────────────────────────────────

    def _call_anthropic(self, prompt: str, max_tokens: int) -> str:
        try:
            import anthropic
        except ImportError:
            print("❌ anthropic not installed. Run: pip install anthropic")
            sys.exit(1)
        client = anthropic.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text

    # ── Google Gemini ─────────────────────────────────────────────────────────

    def _call_gemini(self, prompt: str, max_tokens: int) -> str:
        try:
            import google.generativeai as genai
        except ImportError:
            print("❌ google-generativeai not installed. Run: pip install google-generativeai")
            sys.exit(1)
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            self.model,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
        resp = model.generate_content(prompt)
        return resp.text

    # ── OpenAI ────────────────────────────────────────────────────────────────

    def _call_openai(self, prompt: str, max_tokens: int) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            print("❌ openai not installed. Run: pip install openai")
            sys.exit(1)
        client = OpenAI(api_key=self.api_key)
        resp = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
