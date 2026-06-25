#!/usr/bin/env python3
"""One-off diagnostic: what image generation can THIS Gemini key actually do?

Lists image-capable models the key sees, then attempts a real generation on each
candidate (free experimental -> paid flash-image -> Imagen), printing the exact
outcome (IMAGE OK / no image / the error type+message). Read-only: writes no
files, commits nothing. Run via the gemini-diag workflow.
"""
from __future__ import annotations

import os


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY")
    print(f"GEMINI_API_KEY set: {bool(key)}")
    if not key:
        print("No key — nothing to test.")
        return 0
    try:
        from google import genai
        from google.genai import types
    except Exception as e:  # noqa: BLE001
        print(f"google-genai import failed: {e}")
        return 0
    c = genai.Client(api_key=key)

    print("\n=== models the key can see that mention image/imagen ===")
    try:
        for m in c.models.list():
            name = getattr(m, "name", "").split("/")[-1]
            if "image" in name.lower() or "imagen" in name.lower():
                actions = (getattr(m, "supported_actions", None)
                           or getattr(m, "supported_generation_methods", None))
                print(f"  {name}  actions={actions}")
    except Exception as e:  # noqa: BLE001
        print(f"  models.list() error: {type(e).__name__}: {e}")

    prompt = ("A bold cinematic poster of a dramatic wildfire, vibrant, "
              "high-contrast, vertical 9:16, no text.")
    gen_models = [
        "gemini-2.0-flash-exp-image-generation",
        "gemini-2.0-flash-preview-image-generation",
        "gemini-2.5-flash-image",
        "gemini-2.5-flash-image-preview",
    ]
    print("\n=== generate_content attempts (text+image) ===")
    for model in gen_models:
        try:
            resp = c.models.generate_content(
                model=model, contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"]))
            got = any(getattr(getattr(p, "inline_data", None), "data", None)
                      for p in resp.candidates[0].content.parts)
            print(f"  {model}: {'IMAGE OK' if got else 'no image in response'}")
        except Exception as e:  # noqa: BLE001
            print(f"  {model}: ERROR {type(e).__name__}: {str(e)[:200]}")

    print("\n=== Imagen generate_images attempts ===")
    for model in ("imagen-3.0-generate-002", "imagen-4.0-generate-001"):
        try:
            resp = c.models.generate_images(model=model, prompt=prompt)
            n = len(getattr(resp, "generated_images", []) or [])
            print(f"  {model}: {'IMAGE OK' if n else 'no image'} (count={n})")
        except Exception as e:  # noqa: BLE001
            print(f"  {model}: ERROR {type(e).__name__}: {str(e)[:200]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
