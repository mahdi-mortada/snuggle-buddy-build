"""Patch twscrape xclid.py to support X's new JavaScript bundling format.

X changed their JS from named scripts (ondemand.s.*.js) to numbered chunks
({1:"16327fd",...}[e]+"a.js") in early 2025. This patch updates the two
functions that parse the X homepage JS to extract XClientTxId parameters.

Run once after `pip install twscrape`:
    python patch_twscrape.py
"""
import site
import os
import re

def find_xclid():
    for sp in site.getsitepackages():
        path = os.path.join(sp, "twscrape", "xclid.py")
        if os.path.exists(path):
            return path
    return None

def patch():
    path = find_xclid()
    if not path:
        print("twscrape not installed — nothing to patch")
        return

    with open(path) as f:
        content = f.read()

    already_patched = "# [PATCHED: new X JS format]" in content
    if already_patched:
        print("Already patched")
        return

    # ── Patch 1: get_scripts_list ────────────────────────────────────────────
    old_scripts = (
        'def get_scripts_list(text: str):\n'
        '    scripts = text.split(\'e=>e+"."+\')[1].split(\'[e]+"a.js"\')[0]\n'
        '    try:\n'
        '        for k, v in json.loads(scripts).items():\n'
        '            yield script_url(k, f"{v}a")\n'
        '    except json.decoder.JSONDecodeError as e:\n'
        '        raise Exception("Failed to parse scripts") from e'
    )

    new_scripts = (
        'def get_scripts_list(text: str):  # [PATCHED: new X JS format]\n'
        '    # Old format: e=>e+"."+{...}[e]+"a.js"\n'
        '    if \'e=>e+"."+\' in text:\n'
        '        scripts = text.split(\'e=>e+"."+\')[1].split(\'[e]+"a.js"\')[0]\n'
        '        try:\n'
        '            for k, v in json.loads(scripts).items():\n'
        '                yield script_url(k, f"{v}a")\n'
        '            return\n'
        '        except json.decoder.JSONDecodeError:\n'
        '            pass\n'
        '\n'
        '    # New format (2025+): {...}[e]+"a.js" with unquoted int/sci-notation keys\n'
        '    import re as _re\n'
        '    pattern = _re.compile(r\'\\\\{([^{}]+)\\\\}\\\\[e\\\\]\\\\+"a\\\\.js"\')\n'
        '    match = pattern.search(text)\n'
        '    if match:\n'
        '        raw = match.group(1)\n'
        '        def _expand_key(m):\n'
        '            k = m.group(1)\n'
        '            if \'e\' in k.lower():\n'
        '                try:\n'
        '                    return \'"\' + str(int(float(k))) + \'":\'  # 88e3 -> "88000":\n'
        '                except Exception:\n'
        '                    return \'"\' + k + \'":\'  # keep as-is\n'
        '            return \'"\' + k + \'":\'  # plain int -> quoted\n'
        '        json_str = _re.sub(r\'([\\\\de]+):\', _expand_key, \'{\' + raw + \'}\')\n'
        '        try:\n'
        '            for k, v in json.loads(json_str).items():\n'
        '                yield script_url(k, f"{v}a")\n'
        '            return\n'
        '        except json.decoder.JSONDecodeError as e:\n'
        '            raise Exception("Failed to parse scripts (new format)") from e\n'
        '\n'
        '    raise Exception("Failed to parse scripts: no known format found")'
    )

    # ── Patch 2: parse_anim_idx ───────────────────────────────────────────────
    old_anim = (
        'async def parse_anim_idx(text: str) -> list[int]:\n'
        '    scripts = list(get_scripts_list(text))\n'
        '    scripts = [x for x in scripts if "/ondemand.s." in x]\n'
        '    if not scripts:\n'
        '        raise Exception("Couldn\'t get XClientTxId scripts")\n'
        '\n'
        '    text = await get_tw_page_text(scripts[0])\n'
        '\n'
        '    items = [int(x.group(2)) for x in INDICES_REGEX.finditer(text)]\n'
        '    if not items:\n'
        '        raise Exception("Couldn\'t get XClientTxId indices")\n'
        '\n'
        '    return items'
    )

    new_anim = (
        'async def parse_anim_idx(text: str) -> list[int]:  # [PATCHED: new X JS format]\n'
        '    import re as _re\n'
        '\n'
        '    scripts = list(get_scripts_list(text))\n'
        '\n'
        '    # Old X format: scripts named ondemand.s.*\n'
        '    candidates = [x for x in scripts if "/ondemand.s." in x]\n'
        '\n'
        '    # New X format (2025+): use preloaded named scripts from homepage HTML\n'
        '    if not candidates:\n'
        '        preloaded = _re.findall(\n'
        '            r\'href="(https://abs\\\\.twimg\\\\.com/[^"]+\\\\.js)"\', text\n'
        '        )\n'
        '        candidates = [s for s in preloaded if "/main." in s]\n'
        '        if not candidates:\n'
        '            candidates = [s for s in preloaded if "/vendor." in s]\n'
        '        if not candidates:\n'
        '            candidates = preloaded[:2]\n'
        '\n'
        '    if not candidates:\n'
        '        raise Exception("Couldn\'t get XClientTxId scripts")\n'
        '\n'
        '    script_text = await get_tw_page_text(candidates[0])\n'
        '    items = [int(x.group(2)) for x in INDICES_REGEX.finditer(script_text)]\n'
        '\n'
        '    if not items:\n'
        '        for candidate in candidates[1:]:\n'
        '            script_text = await get_tw_page_text(candidate)\n'
        '            items = [int(x.group(2)) for x in INDICES_REGEX.finditer(script_text)]\n'
        '            if items:\n'
        '                break\n'
        '\n'
        '    if not items:\n'
        '        raise Exception("Couldn\'t get XClientTxId indices")\n'
        '\n'
        '    return items'
    )

    if old_scripts not in content:
        print("WARNING: get_scripts_list patch target not found — may already be patched or version mismatch")
    else:
        content = content.replace(old_scripts, new_scripts)
        print("Patched get_scripts_list")

    if old_anim not in content:
        print("WARNING: parse_anim_idx patch target not found — may already be patched or version mismatch")
    else:
        content = content.replace(old_anim, new_anim)
        print("Patched parse_anim_idx")

    with open(path, "w") as f:
        f.write(content)

    print(f"Done — patched {path}")


if __name__ == "__main__":
    patch()
