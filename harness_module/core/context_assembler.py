"""
Builds the messages list sent to the model for each request.

Responsibilities:
- Look up token budget for the loaded model
- Pick system prompt LOD based on budget tier
- Truncate history to fit (drop oldest first, always keep last 4 messages)
- Leave room for response reservation

Token counting is character-based (~4 chars/token). Imprecise but fast and
conservative — real token counts vary by tokenizer, so this errs small.
"""

from dataclasses import dataclass

CHARS_PER_TOKEN = 4
ROLE_OVERHEAD = 4  # per-message formatting tokens


@dataclass(frozen=True)
class ModelProfile:
    window: int    # context window size
    working: int   # safe working budget (well under window ceiling)
    response: int  # tokens reserved for model output
    lod: int       # system prompt LOD: 0=minimal, 1=full, 2=rich


# Profiles tuned conservatively — hitting the ceiling degrades quality.
# Unknown models fall back to DEFAULT_PROFILE.
MODEL_PROFILES: dict[str, ModelProfile] = {
    "qwen2.5:3b":          ModelProfile(window=32768, working=8000,  response=900,  lod=0),
    "qwen2.5:7b":          ModelProfile(window=32768, working=14000, response=1200, lod=1),
    "qwen2.5:14b":         ModelProfile(window=32768, working=18000, response=1500, lod=2),
    "qwen2.5:32b":         ModelProfile(window=32768, working=22000, response=2000, lod=2),
    "qwen2.5:72b":         ModelProfile(window=32768, working=24000, response=2000, lod=2),
    "llama3.2:1b":         ModelProfile(window=8192,  working=4000,  response=700,  lod=0),
    "llama3.2:3b":         ModelProfile(window=8192,  working=5500,  response=800,  lod=0),
    "llama3.1:8b":         ModelProfile(window=32768, working=14000, response=1200, lod=1),
    "llama3.1:70b":        ModelProfile(window=32768, working=22000, response=2000, lod=2),
    "llama3.3:70b":        ModelProfile(window=32768, working=22000, response=2000, lod=2),
    "dolphin-llama3:8b":   ModelProfile(window=8192,  working=5500,  response=900,  lod=0),
    "dolphin-llama3:70b":  ModelProfile(window=32768, working=22000, response=2000, lod=2),
    "mistral:7b":          ModelProfile(window=32768, working=14000, response=1200, lod=1),
    "gemma2:9b":           ModelProfile(window=8192,  working=5500,  response=900,  lod=1),
    "gemma2:27b":          ModelProfile(window=8192,  working=6000,  response=1000, lod=2),
    "phi3:mini":           ModelProfile(window=4096,  working=3000,  response=700,  lod=0),
    "phi3:medium":         ModelProfile(window=4096,  working=3000,  response=700,  lod=0),
    "phi4:14b":            ModelProfile(window=16384, working=12000, response=1200, lod=1),
}

DEFAULT_PROFILE = ModelProfile(window=4096, working=3000, response=700, lod=0)

# Minimum number of recent messages always kept regardless of budget pressure
MIN_ANCHOR_MESSAGES = 4


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


class ContextAssembler:

    def get_profile(self, model_id: str) -> ModelProfile:
        if model_id in MODEL_PROFILES:
            return MODEL_PROFILES[model_id]
        # Prefix match — handles tag variants like "qwen2.5:7b-instruct-q4_K_M"
        base = model_id.split(":")[0].lower()
        for key, profile in MODEL_PROFILES.items():
            if key.startswith(base):
                return profile
        return DEFAULT_PROFILE

    def get_lod(self, model_id: str) -> int:
        return self.get_profile(model_id).lod

    def assemble(
        self,
        *,
        model_id: str,
        system_prompt: str,
        history: list[dict],  # [{role, content}, ...] oldest first, excludes current msg
        user_message: str,
    ) -> list[dict]:
        """
        Returns the trimmed history list to pass as `messages` to the backend.
        The system_prompt is passed separately; user_message is the final entry.
        Caller appends the user message after this returns.
        """
        profile = self.get_profile(model_id)

        fixed_tokens = (
            _estimate_tokens(system_prompt)
            + _estimate_tokens(user_message)
            + profile.response
            + ROLE_OVERHEAD * 2  # system + current user
        )
        history_budget = profile.working - fixed_tokens

        if not history or history_budget <= 0:
            return []

        # Anchor: always keep the most recent N messages
        anchor = history[-MIN_ANCHOR_MESSAGES:]
        rest = history[:-MIN_ANCHOR_MESSAGES] if len(history) > MIN_ANCHOR_MESSAGES else []

        anchor_tokens = sum(
            _estimate_tokens(m["content"]) + ROLE_OVERHEAD for m in anchor
        )
        remaining = history_budget - anchor_tokens

        # Fill additional history working backwards from just before the anchor
        extra: list[dict] = []
        for msg in reversed(rest):
            cost = _estimate_tokens(msg["content"]) + ROLE_OVERHEAD
            if remaining - cost < 0:
                break
            extra.insert(0, msg)
            remaining -= cost

        return extra + anchor

    def budget_summary(self, model_id: str, system_prompt: str) -> dict:
        """Diagnostic info — useful for logging/debugging."""
        profile = self.get_profile(model_id)
        sys_tokens = _estimate_tokens(system_prompt)
        return {
            "model_id": model_id,
            "working_budget": profile.working,
            "response_reserve": profile.response,
            "system_tokens_est": sys_tokens,
            "history_budget_est": profile.working - sys_tokens - profile.response,
            "lod": profile.lod,
        }


# Module-level singleton — stateless, safe to share
assembler = ContextAssembler()
