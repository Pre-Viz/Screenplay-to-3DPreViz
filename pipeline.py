#!/usr/bin/env python3
"""
Full Pre-Vis Pipeline
=====================

Runs Phase 1 (scene) + Phase 2 (cameras) in one command.

Usage:
    python3 pipeline.py --file script.txt
    python3 pipeline.py "INT. KITCHEN - DAY\\n\\nADRIANA washes dishes..."
    python3 pipeline.py --file script.txt --output my_scene
    python3 pipeline.py --file script.txt --scene-only     # Phase 1 only
    python3 pipeline.py --file script.txt --cameras-only   # Phase 2 only (needs --blend + --json)

Output files:
    <name>.json                  Phase 1 scene config
    <name>.blend                 Phase 1 scene (characters, environment, props)
    <name>_cameras.json          Phase 2 camera shots plan
    <name>_cameras.blend         Final scene with cameras + timeline markers
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared setup
# ---------------------------------------------------------------------------

def _read_file(path: str) -> str:
    """Read a screenplay from a .pdf, .txt, .fountain, or any plain-text file."""
    p = Path(path)
    if not p.exists():
        print(f"❌ File not found: {path}")
        sys.exit(1)

    ext = p.suffix.lower()

    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print("❌ pypdf not installed. Run: pip install pypdf")
            sys.exit(1)
        reader = PdfReader(str(p))
        pages  = [page.extract_text() or "" for page in reader.pages]
        text   = "\n".join(pages)
        print(f"📄 Read PDF: {p.name}  ({len(reader.pages)} pages, {len(text)} chars)")
        return text

    # .txt, .fountain, .fdx (plain text export), or anything else — read as UTF-8
    text = p.read_text(encoding="utf-8", errors="replace")
    print(f"📄 Read file: {p.name}  ({len(text)} chars)")
    return text


def _resolve_screenplay(args, required: bool = True) -> str | None:
    """Return screenplay text, or None if not provided and not required."""
    if args.file:
        return _read_file(args.file)
    elif args.screenplay:
        return args.screenplay
    elif required:
        print("📝 Paste screenplay text (Ctrl+D when done):")
        try:
            return sys.stdin.read()
        except KeyboardInterrupt:
            print("\n👋 Cancelled.")
            sys.exit(0)
    else:
        return None


def _safe_name(scene_name: str) -> str:
    import re
    return re.sub(r'[^a-zA-Z0-9_]', '_', scene_name).lower().strip('_')


# ---------------------------------------------------------------------------
# Phase 1
# ---------------------------------------------------------------------------

def _read_notes(text: str | None, path: str | None) -> str | None:
    """Director's notes from --direction/--shotlist text or their *-file variants."""
    if path:
        return Path(path).read_text()
    return text


def run_phase1(screenplay: str, output_dir: Path, output_name: str = None, backend: str = "auto", model: str = None,
               direction: str = None) -> tuple[str, str]:
    """
    Returns (json_path, blend_path).
    """
    print("\n" + "=" * 60)
    print("  PHASE 1 — Scene Generation")
    print("=" * 60)

    sys.path.insert(0, str(Path(__file__).parent))
    from screenplay_to_scene import ScreenplayToScene

    generator = ScreenplayToScene(backend=backend, model=model)
    data      = generator.generate_json(screenplay, direction)
    if not data:
        print("❌ Phase 1: JSON generation failed.")
        sys.exit(1)

    data = generator._postprocess(data)

    # Determine output name
    if output_name is None:
        output_name = _safe_name(data["scene"]["name"])

    json_path  = str(output_dir / f"{output_name}.json")
    blend_path = str(output_dir / f"{output_name}.blend")

    # Asset paths in the JSON are relative to the repo; the generator resolves them
    # relative to the JSON's folder unless told otherwise, and the JSON lives in output/.
    data.setdefault("settings", {})["asset_base_path"] = str(Path(__file__).parent.absolute())

    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\n💾 Scene JSON : {json_path}")

    # Save screenplay alongside JSON so Phase 2 can pick it up automatically
    screenplay_path = json_path.replace(".json", "_screenplay.txt")
    Path(screenplay_path).write_text(screenplay)
    print(f"💾 Screenplay  : {screenplay_path}")

    from flexible_scene_generator_optimized import OptimizedSceneGenerator
    ok = OptimizedSceneGenerator(json_path).generate_scene(blend_path, render_video=False)
    if not ok:
        print("❌ Phase 1: Blender scene generation failed.")
        sys.exit(1)

    print(f"✅ Scene blend: {blend_path}")
    return json_path, blend_path


# ---------------------------------------------------------------------------
# Phase 2
# ---------------------------------------------------------------------------

def run_phase2(
    screenplay:    str | None,
    json_path:     str,
    blend_path:    str,
    output_dir:    Path,
    output_name:   str,
    backend:       str = "auto",
    model:         str = None,
    shots_json_in: str = None,
    shotlist:      str = None,
) -> str:
    """
    Returns cameras_blend_path.
    """
    print("\n" + "=" * 60)
    print("  PHASE 2 — Camera Setup")
    print("=" * 60)

    from camera_setup import CameraSetup

    with open(json_path) as f:
        scene_json = json.load(f)

    cameras_blend = str(output_dir / f"{output_name}_cameras.blend")

    setup = CameraSetup(backend=backend, model=model)

    # Print the beat timeline so user can see what Groq is working with
    events = setup._extract_animation_events(scene_json)
    print("\n📋 Animation beat timeline:")
    for e in events:
        flag = "MOVING" if e["moving"] else "action change"
        print(f"   t={e['second']:>5.1f}s  {e['character']:<12} → {e['action']:<25} [{flag}]")

    ok = setup.run(
        screenplay    = screenplay,
        scene_json    = scene_json,
        blend_in      = blend_path,
        blend_out     = cameras_blend,
        shots_json_in = shots_json_in,
        direction     = shotlist,
    )
    if not ok:
        print("❌ Phase 2: Camera setup failed.")
        sys.exit(1)

    return cameras_blend


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Full pre-vis pipeline: screenplay → scene → cameras.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 pipeline.py "INT. KITCHEN - DAY\\n\\nADRIANA and RAUL argue."
  python3 pipeline.py --file script.txt
  python3 pipeline.py --file script.txt --output kitchen_fight
  python3 pipeline.py --file script.txt --scene-only
  python3 pipeline.py --regen --json int__bar___night.json
  python3 pipeline.py --blend scene.blend --json scene.json --cameras-only
        """,
    )
    parser.add_argument("screenplay",       nargs="?",            help="Inline screenplay text")
    parser.add_argument("--file",    "-f",                        help="Path to screenplay (.txt, .pdf, .fountain)")
    parser.add_argument("--output",  "-o",                        help="Base output name (no extension)")
    parser.add_argument("--scene-only",     action="store_true",  help="Run Phase 1 only")
    parser.add_argument("--cameras-only",   action="store_true",  help="Run Phase 2 only (needs --blend + --json)")
    parser.add_argument("--regen",          action="store_true",  help="Skip Groq — regenerate .blend from an existing (edited) JSON")
    parser.add_argument("--blend",   "-b",                        help="Existing .blend (for --cameras-only)")
    parser.add_argument("--json",    "-j",                        help="Existing scene .json (for --cameras-only or --regen)")
    parser.add_argument("--backend", "-B",  default="auto",       help="LLM backend: groq | anthropic | gemini | openai (default: auto-detect from API keys)")
    parser.add_argument("--model",          default=None,         help="Override model name for chosen backend")
    parser.add_argument("--cameras-json",                         help="Skip LLM — use a pre-written camera shots JSON for Phase 2")
    parser.add_argument("--direction",                            help="Phase 1 director's notes: characters, blocking and beat timings, "
                                                                       "e.g. \"A and B talk for 3 s, then A turns away for 2 s, then B walks past A\"")
    parser.add_argument("--direction-file",                       help="Phase 1 director's notes from a text file")
    parser.add_argument("--shotlist",                             help="Phase 2 shot list in plain words, e.g. \"wide until he arrives, then CU on him, then CU on her\"")
    parser.add_argument("--shotlist-file",                        help="Phase 2 shot list from a text file")
    args = parser.parse_args()

    output_dir  = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    output_name = args.output

    print("=" * 60)
    print("🎬  FULL PRE-VIS PIPELINE")
    print("=" * 60)

    # --- Regen blend from edited JSON (skip Groq entirely) ---
    if args.regen:
        if not args.json:
            print("❌ --regen requires --json <path-to-edited-json>")
            sys.exit(1)
        json_path  = args.json
        blend_path = json_path.replace(".json", ".blend")
        if output_name:
            blend_path = str(output_dir / f"{output_name}.blend")
        print(f"\n🔄 Regenerating blend from: {json_path}")
        sys.path.insert(0, str(Path(__file__).parent))
        from flexible_scene_generator_optimized import OptimizedSceneGenerator
        ok = OptimizedSceneGenerator(json_path).generate_scene(blend_path, render_video=False)
        if ok:
            print(f"✅ Done: {blend_path}")
        else:
            print("❌ Blend generation failed.")
            sys.exit(1)
        return

    # --- Phase 2 only ---
    if args.cameras_only:
        if not args.blend or not args.json:
            print("❌ --cameras-only requires --blend and --json")
            sys.exit(1)
        # Auto-load the screenplay saved by Phase 1 (next to the JSON)
        screenplay = _resolve_screenplay(args, required=False)
        if not screenplay:
            saved = Path(args.json).with_suffix("").as_posix() + "_screenplay.txt"
            if Path(saved).exists():
                screenplay = Path(saved).read_text()
                print(f"📖 Screenplay  : loaded from {saved}")
            else:
                print("No screenplay found — Groq will plan cameras from the beat timeline only.")
        else:
            print(f"Screenplay: {len(screenplay)} characters (used for camera context)")
        if output_name is None:
            output_name = Path(args.blend).stem
        run_phase2(screenplay, args.json, args.blend, output_dir, output_name,
                   backend=args.backend, model=args.model,
                   shots_json_in=args.cameras_json,
                   shotlist=_read_notes(args.shotlist, args.shotlist_file))
        return

    # --- Phase 1 (screenplay required) ---
    screenplay = _resolve_screenplay(args, required=True)
    print(f"Screenplay: {len(screenplay)} characters")
    json_path, blend_path = run_phase1(screenplay, output_dir, output_name,
                                       backend=args.backend, model=args.model,
                                       direction=_read_notes(args.direction, args.direction_file))
    if output_name is None:
        output_name = Path(blend_path).stem

    if args.scene_only:
        print(f"\n✅ Scene only — done.\n   {blend_path}")
        return

    # --- Phase 2 ---
    cameras_blend = run_phase2(screenplay, json_path, blend_path, output_dir, output_name,
                               backend=args.backend, model=args.model,
                               shotlist=_read_notes(args.shotlist, args.shotlist_file))

    print("\n" + "=" * 60)
    print("✅ PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Scene  : {blend_path}")
    print(f"  Cameras: {cameras_blend}")
    print()
    print("Open the _cameras.blend in Blender.")
    print("Press Space — timeline markers auto-cut between cameras.")


if __name__ == "__main__":
    main()
