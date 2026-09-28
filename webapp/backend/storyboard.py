"""Parse the same '## Scene' storyboard text format Reel Forge's paste box
uses, so a storyboard written/edited there can be pasted here unchanged.

There is no server-side AI storyboard generation in this app -- that would
need an Anthropic API key this deployment doesn't hold. The caller supplies
the full storyboard text (or the app falls back to a bundled example).
"""
import re

_KIND_MAP = {
    "title": "title", "title card": "title",
    "bullets": "bullets", "bullet list": "bullets",
    "flow": "flow", "process": "flow", "process flow": "flow",
    "stat": "stat", "quote": "stat", "stat / quote": "stat", "stat/quote": "stat",
    "outro": "outro",
}

_LINE_RE = re.compile(r"^\s*([A-Za-z]+)\s*:\s*(.*)$")


class StoryboardError(ValueError):
    pass


def parse(text):
    blocks = [b.strip() for b in re.split(r"\n(?=##\s)", text) if b.strip()]
    if not blocks:
        raise StoryboardError('no "## Scene" blocks found')

    scenes = []
    for block in blocks:
        lines = block.split("\n")
        head_line = re.sub(r"^##\s*", "", lines[0]).strip().lower()
        kind = _KIND_MAP.get(head_line, "bullets")
        scene = {"kind": kind, "heading": "", "bullets": [], "nodes": [], "stat": "", "narration": ""}
        for line in lines[1:]:
            m = _LINE_RE.match(line)
            if not m:
                continue
            key, val = m.group(1).lower(), m.group(2).strip()
            if key == "heading":
                scene["heading"] = val
            elif key == "bullets":
                scene["bullets"] = [x.strip() for x in val.split("|") if x.strip()]
            elif key == "nodes":
                scene["nodes"] = [x.strip() for x in val.split("|") if x.strip()]
            elif key == "stat":
                scene["stat"] = val
            elif key == "narration":
                scene["narration"] = val
        if not scene["heading"]:
            raise StoryboardError(f'scene missing "Heading:" ({block[:40]}...)')
        if not scene["narration"]:
            raise StoryboardError(f'scene missing "Narration:" ({block[:40]}...)')
        scenes.append(scene)
    return scenes


EXAMPLE = """## Title Card
Heading: How Photosynthesis Works
Narration: Ever wonder how a leaf turns sunlight into food?

## Bullets
Heading: What a plant needs
Bullets: Sunlight | Water | Carbon dioxide
Narration: Just three ingredients: sunlight, water, and carbon dioxide.

## Flow
Heading: Inside the leaf
Nodes: Light hits the leaf | Water and CO2 combine | Sugar and oxygen made
Narration: Light energy drives a reaction that turns water and carbon dioxide into sugar and oxygen.

## Stat
Heading: Why it matters
Stat: Plants make nearly all of Earth's breathable oxygen.
Narration: That oxygen is most of what we breathe.

## Outro
Heading: That's the whole story
Narration: That's photosynthesis, in a nutshell.
"""
