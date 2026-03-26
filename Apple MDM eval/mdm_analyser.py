#!/usr/bin/env python3
"""
mdm_analyser.py
---------------
Analyses an Apple MDM Restrictions profile (.xml / .mobileconfig / .plist)
against a YAML restriction reference and produces an HTML report.

Usage:
    python mdm_analyser.py <profile.xml> [--ref restriction_reference.yaml]
                           [--out report.html] [--no-lookup]

Requirements:
    pip install pyyaml requests
"""

import argparse
import json
import os
import plistlib
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("Missing dependency: pip install pyyaml")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Default paths (same directory as script) ─────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
DEFAULT_REF = SCRIPT_DIR / "restriction_reference.yaml"

# ── App Store lookup ──────────────────────────────────────────────────────────
ITUNES_LOOKUP = "https://itunes.apple.com/lookup?bundleId={}&country=us"
LOOKUP_DELAY  = 0.3   # seconds between requests to avoid rate limiting


def lookup_bundle_id(bundle_id: str, cache: dict) -> str:
    """Return app name for a bundle ID, using cache. Returns None if not found."""
    if bundle_id in cache:
        return cache[bundle_id]
    if not HAS_REQUESTS:
        cache[bundle_id] = None
        return None
    try:
        url = ITUNES_LOOKUP.format(bundle_id)
        r = requests.get(url, timeout=5)
        data = r.json()
        if data.get("resultCount", 0) > 0:
            name = data["results"][0].get("trackName", None)
            cache[bundle_id] = name
            return name
    except Exception:
        pass
    cache[bundle_id] = None
    return None


# ── Profile parsing ───────────────────────────────────────────────────────────

def load_profile(path: str) -> dict:
    """Load a .xml / .mobileconfig / .plist file and return the plist dict."""
    with open(path, "rb") as f:
        return plistlib.load(f)


def extract_restrictions(profile: dict) -> tuple[dict, dict]:
    """
    Walk PayloadContent and return:
      - restrictions : flat key→value dict of the com.apple.applicationaccess payload
      - meta         : top-level profile metadata
    """
    meta = {
        "PayloadDisplayName": profile.get("PayloadDisplayName", "Unknown"),
        "PayloadDescription": profile.get("PayloadDescription", ""),
        "PayloadOrganization": profile.get("PayloadOrganization", ""),
        "PayloadUUID": profile.get("PayloadUUID", ""),
        "PayloadRemovalDisallowed": profile.get("PayloadRemovalDisallowed", None),
    }

    restrictions = {}
    # Inject top-level PayloadRemovalDisallowed so conflict rules can reference it
    if meta["PayloadRemovalDisallowed"] is not None:
        restrictions["PayloadRemovalDisallowed"] = meta["PayloadRemovalDisallowed"]

    for payload in profile.get("PayloadContent", []):
        if payload.get("PayloadType") == "com.apple.applicationaccess":
            for k, v in payload.items():
                if not k.startswith("Payload"):
                    restrictions[k] = v
    return restrictions, meta


# ── Reference loading ─────────────────────────────────────────────────────────

def load_reference(ref_path: str) -> tuple[dict, list]:
    """Return (restrictions_by_key, conflict_rules)."""
    with open(ref_path, "r") as f:
        data = yaml.safe_load(f)
    by_key = {r["key"]: r for r in data.get("restrictions", [])}
    rules  = data.get("conflict_rules", [])
    return by_key, rules


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyse_deprecated(restrictions: dict, ref: dict) -> list:
    """Return list of dicts for keys that are present in profile AND deprecated."""
    findings = []
    for key, value in restrictions.items():
        r = ref.get(key)
        if r and r.get("deprecated"):
            findings.append({
                "key":   key,
                "value": value,
                "since": r.get("deprecated_since", "unknown"),
                "note":  r.get("deprecated_note", ""),
                "category": r.get("category", ""),
            })
    return sorted(findings, key=lambda x: x["category"])


def analyse_insecure(restrictions: dict, ref: dict) -> dict:
    """
    Return dict of category → list of findings.
    Excludes deprecated keys.
    """
    by_category = defaultdict(list)
    for key, value in restrictions.items():
        r = ref.get(key)
        if not r:
            continue
        if r.get("deprecated"):
            continue  # deprecated handled separately
        insecure_val = r.get("insecure_if_value")
        if insecure_val is None:
            continue
        # Compare — handle integer vs string edge cases
        if value == insecure_val or str(value) == str(insecure_val):
            by_category[r.get("category", "Uncategorized")].append({
                "key":      key,
                "value":    value,
                "severity": r.get("insecure_severity", "LOW"),
                "note":     r.get("insecure_note", ""),
            })
    # Special case: enforcedSoftwareUpdateDelay — insecure if >= 60 (but not deprecated on this profile version)
    delay_key = "enforcedSoftwareUpdateDelay"
    if delay_key in restrictions:
        r = ref.get(delay_key)
        if r and not r.get("deprecated"):
            val = restrictions[delay_key]
            if isinstance(val, int) and val >= 60:
                by_category[r.get("category", "Device")].append({
                    "key":      delay_key,
                    "value":    val,
                    "severity": "HIGH",
                    "note":     r.get("insecure_note", f"Update delay of {val} days is excessive."),
                })

    # Sort within each category by severity
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    for cat in by_category:
        by_category[cat].sort(key=lambda x: sev_order.get(x["severity"], 9))

    return dict(by_category)


def analyse_conflicts(restrictions: dict, rules: list) -> list:
    """Return list of triggered conflict rules."""
    triggered = []
    for rule in rules:
        conditions = rule.get("conditions", [])
        if not conditions:
            continue
        all_match = True
        for cond in conditions:
            key   = cond["key"]
            op    = cond.get("op", "eq")
            val   = cond["value"]
            actual = restrictions.get(key, "__NOT_PRESENT__")

            if actual == "__NOT_PRESENT__":
                # For PayloadRemovalDisallowed: treat absent as false
                if key == "PayloadRemovalDisallowed":
                    actual = False
                else:
                    all_match = False
                    break

            if op == "eq"  and actual != val: all_match = False; break
            if op == "ne"  and actual == val: all_match = False; break
            if op == "gt"  and not (isinstance(actual, (int,float)) and actual >  val): all_match = False; break
            if op == "lt"  and not (isinstance(actual, (int,float)) and actual <  val): all_match = False; break

        if all_match:
            triggered.append(rule)

    return sorted(triggered, key=lambda x: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,"LOW":3}.get(x.get("severity","LOW"),9))


def analyse_apps(restrictions: dict, do_lookup: bool) -> tuple[list, list]:
    """Return (allowed_apps, blocked_apps) each as list of {bundle_id, name}."""
    allowed_ids = restrictions.get("allowListedAppBundleIDs", [])
    blocked_ids = restrictions.get("blockedAppBundleIDs",     [])

    cache = {}

    def resolve(bundle_ids):
        results = []
        for bid in bundle_ids:
            name = None
            if do_lookup:
                name = lookup_bundle_id(bid, cache)
                time.sleep(LOOKUP_DELAY)
            results.append({
                "bundle_id": bid,
                "name": name if name else "Internal / Unknown",
                "resolved": name is not None,
            })
        return sorted(results, key=lambda x: x["bundle_id"])

    return resolve(allowed_ids), resolve(blocked_ids)


# ── HTML Report ───────────────────────────────────────────────────────────────

SEV_COLOUR = {
    "CRITICAL": ("#7f1d1d", "#fee2e2", "⬛"),
    "HIGH":     ("#7c2d12", "#ffedd5", "🔴"),
    "MEDIUM":   ("#78350f", "#fef9c3", "🟡"),
    "LOW":      ("#1e3a5f", "#dbeafe", "🔵"),
}

def sev_badge(severity: str) -> str:
    fg, bg, _ = SEV_COLOUR.get(severity, ("#374151", "#f3f4f6", ""))
    return f'<span class="badge" style="background:{bg};color:{fg}">{severity}</span>'

def esc(s) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def bool_pill(v) -> str:
    if v is True:
        return '<span class="pill pill-true">true</span>'
    if v is False:
        return '<span class="pill pill-false">false</span>'
    return f'<code>{esc(v)}</code>'


def build_html(
    meta: dict,
    deprecated: list,
    insecure: dict,
    conflicts: list,
    allowed_apps: list,
    blocked_apps: list,
    profile_path: str,
    do_lookup: bool,
) -> str:

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    profile_name = esc(meta.get("PayloadDisplayName","Unknown"))
    profile_desc = esc(meta.get("PayloadDescription",""))
    profile_org  = esc(meta.get("PayloadOrganization",""))
    profile_uuid = esc(meta.get("PayloadUUID",""))
    removal_flag = meta.get("PayloadRemovalDisallowed")

    total_deprecated = len(deprecated)
    total_insecure   = sum(len(v) for v in insecure.values())
    total_conflicts  = len(conflicts)

    # Count by severity across insecure findings
    sev_counts = defaultdict(int)
    for findings in insecure.values():
        for f in findings:
            sev_counts[f["severity"]] += 1
    for f in conflicts:
        sev_counts[f.get("severity","LOW")] += 1

    def stat_box(label, value, colour):
        return f'''
        <div class="stat-box" style="border-left:4px solid {colour}">
          <div class="stat-num">{value}</div>
          <div class="stat-label">{label}</div>
        </div>'''

    # ── deprecated rows ──────────────────────────────────────────────────────
    dep_rows = ""
    if deprecated:
        for d in deprecated:
            dep_rows += f"""
            <tr>
              <td><code>{esc(d['key'])}</code></td>
              <td>{esc(d['category'])}</td>
              <td>{bool_pill(d['value'])}</td>
              <td>{esc(d['since'])}</td>
              <td class="note-cell">{esc(d['note'])}</td>
            </tr>"""
    else:
        dep_rows = '<tr><td colspan="5" class="empty-row">No deprecated restrictions found.</td></tr>'

    # ── insecure sections ────────────────────────────────────────────────────
    insecure_html = ""
    if insecure:
        for cat, findings in sorted(insecure.items()):
            rows = ""
            for f in findings:
                fg, bg, icon = SEV_COLOUR.get(f['severity'], ("#374151","#f3f4f6",""))
                rows += f"""
                <tr>
                  <td>{sev_badge(f['severity'])}</td>
                  <td><code>{esc(f['key'])}</code></td>
                  <td>{bool_pill(f['value'])}</td>
                  <td class="note-cell">{esc(f['note'])}</td>
                </tr>"""
            insecure_html += f"""
            <div class="category-block">
              <h3 class="cat-heading">{esc(cat)}</h3>
              <table>
                <thead><tr>
                  <th style="width:100px">Severity</th>
                  <th>Key</th>
                  <th style="width:80px">Value</th>
                  <th>Finding</th>
                </tr></thead>
                <tbody>{rows}</tbody>
              </table>
            </div>"""
    else:
        insecure_html = '<p class="empty-msg">No insecure configurations detected.</p>'

    # ── conflict rows ────────────────────────────────────────────────────────
    conflict_rows = ""
    if conflicts:
        for c in conflicts:
            fg, bg, _ = SEV_COLOUR.get(c.get('severity','LOW'), ("#374151","#f3f4f6",""))
            cond_list = "".join(
                f"<li><code>{esc(x['key'])}</code> {esc(x['op'])} <code>{esc(x['value'])}</code></li>"
                for x in c.get("conditions", [])
            )
            conflict_rows += f"""
            <div class="conflict-card" style="border-left:4px solid {fg}">
              <div class="conflict-header">
                {sev_badge(c.get('severity','LOW'))}
                <span class="conflict-id">{esc(c.get('id',''))}</span>
                <strong>{esc(c.get('description',''))}</strong>
              </div>
              <p class="note-cell">{esc(c.get('note',''))}</p>
              <details>
                <summary>Triggering conditions</summary>
                <ul>{cond_list}</ul>
              </details>
            </div>"""
    else:
        conflict_rows = '<p class="empty-msg">No conflicting configurations detected.</p>'

    # ── app tables ────────────────────────────────────────────────────────────
    def app_table(apps, label, colour):
        if not apps:
            return f'<p class="empty-msg">No {label.lower()} apps defined.</p>'
        rows = ""
        for a in apps:
            name_cell = esc(a['name'])
            if not a['resolved']:
                name_cell = f'<span class="internal-tag">{name_cell}</span>'
            rows += f"<tr><td><code>{esc(a['bundle_id'])}</code></td><td>{name_cell}</td></tr>"
        lookup_note = "" if do_lookup else '<p class="lookup-note">ℹ App name lookup was disabled (use without --no-lookup to enable).</p>'
        return f"""
        {lookup_note}
        <table>
          <thead><tr>
            <th>Bundle ID</th>
            <th>App Name</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>"""

    allowed_table = app_table(allowed_apps, "Allowed", "#15803d")
    blocked_table = app_table(blocked_apps, "Blocked", "#b91c1c")

    removal_warning = ""
    if removal_flag is False or removal_flag is None:
        removal_warning = """
        <div class="removal-warning">
          ⚠️ <strong>PayloadRemovalDisallowed is false or absent.</strong>
          This profile can be removed by the user without MDM authorization,
          rendering all restrictions ineffective.
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MDM Profile Analysis – {profile_name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap');

  :root {{
    --bg:       #0f1117;
    --surface:  #1a1d27;
    --surface2: #222636;
    --border:   #2e3347;
    --text:     #e2e4ef;
    --text-dim: #8b90a8;
    --accent:   #4f8ef7;
    --mono:     'IBM Plex Mono', monospace;
    --sans:     'IBM Plex Sans', sans-serif;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: var(--sans);
    background: var(--bg);
    color: var(--text);
    font-size: 14px;
    line-height: 1.6;
  }}

  /* ── header ── */
  .header {{
    background: linear-gradient(135deg, #0e1628 0%, #1a2744 100%);
    border-bottom: 1px solid #2a3a60;
    padding: 32px 40px 24px;
  }}
  .header-top {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
  }}
  .header h1 {{
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.3px;
    color: #c9d8ff;
  }}
  .header .subtitle {{
    font-size: 12px;
    color: var(--text-dim);
    margin-top: 4px;
    font-family: var(--mono);
  }}
  .meta-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 18px;
  }}
  .chip {{
    background: #1e2d50;
    border: 1px solid #2a3f6a;
    border-radius: 4px;
    padding: 3px 10px;
    font-size: 11px;
    font-family: var(--mono);
    color: #93a8d4;
  }}
  .chip strong {{ color: #c9d8ff; }}
  .report-time {{
    font-size: 11px;
    color: var(--text-dim);
    font-family: var(--mono);
    white-space: nowrap;
  }}

  /* ── removal warning ── */
  .removal-warning {{
    background: #3b0a0a;
    border: 1px solid #7f1d1d;
    border-radius: 6px;
    padding: 14px 18px;
    margin: 24px 40px 0;
    color: #fca5a5;
    font-size: 13px;
    line-height: 1.5;
  }}

  /* ── stats bar ── */
  .stats-bar {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
    padding: 20px 40px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }}
  .stat-box {{
    background: var(--surface2);
    border-radius: 6px;
    padding: 12px 20px;
    min-width: 130px;
    flex: 1;
  }}
  .stat-num {{
    font-size: 28px;
    font-weight: 600;
    font-family: var(--mono);
    color: var(--text);
    line-height: 1;
  }}
  .stat-label {{
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-top: 4px;
  }}
  .sev-row {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    padding: 8px 40px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }}
  .sev-item {{
    font-size: 12px;
    font-family: var(--mono);
    padding: 2px 8px;
    border-radius: 3px;
  }}

  /* ── nav ── */
  nav {{
    background: var(--surface2);
    border-bottom: 1px solid var(--border);
    padding: 0 40px;
    display: flex;
    gap: 0;
    overflow-x: auto;
  }}
  nav a {{
    display: block;
    padding: 12px 18px;
    color: var(--text-dim);
    text-decoration: none;
    font-size: 13px;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
  }}
  nav a:hover {{ color: var(--text); border-color: var(--accent); }}

  /* ── main content ── */
  main {{
    padding: 32px 40px;
    max-width: 1300px;
  }}

  section {{
    margin-bottom: 48px;
  }}

  h2 {{
    font-size: 17px;
    font-weight: 600;
    color: #c9d8ff;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  h2 .count-badge {{
    font-size: 12px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1px 9px;
    color: var(--text-dim);
    font-family: var(--mono);
    font-weight: 400;
  }}

  h3.cat-heading {{
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: var(--accent);
    margin: 24px 0 10px;
  }}

  /* ── tables ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    margin-bottom: 8px;
  }}
  th {{
    background: var(--surface2);
    color: var(--text-dim);
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    padding: 9px 14px;
    text-align: left;
    border: 1px solid var(--border);
  }}
  td {{
    padding: 9px 14px;
    border: 1px solid var(--border);
    vertical-align: top;
    color: var(--text);
  }}
  tr:nth-child(even) td {{ background: #161921; }}
  tr:nth-child(odd)  td {{ background: var(--surface); }}
  tr:hover td {{ background: #1e2338; }}

  .note-cell {{
    color: #a9afc8;
    font-size: 12.5px;
    line-height: 1.55;
  }}
  .empty-row, .empty-msg {{
    color: var(--text-dim);
    font-size: 13px;
    padding: 16px 0;
  }}

  code {{
    font-family: var(--mono);
    font-size: 12px;
    background: #1e2338;
    padding: 1px 5px;
    border-radius: 3px;
    color: #93c5fd;
    white-space: nowrap;
  }}

  /* ── pills & badges ── */
  .badge {{
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    font-family: var(--mono);
    padding: 2px 7px;
    border-radius: 3px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .pill {{
    display: inline-block;
    font-family: var(--mono);
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 10px;
    font-weight: 600;
  }}
  .pill-true  {{ background: #14532d; color: #86efac; }}
  .pill-false {{ background: #450a0a; color: #fca5a5; }}
  .internal-tag {{ color: #64748b; font-style: italic; }}

  /* ── conflict cards ── */
  .conflict-card {{
    background: var(--surface);
    border-radius: 6px;
    padding: 16px 18px;
    margin-bottom: 12px;
  }}
  .conflict-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }}
  .conflict-id {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
  }}
  details {{ margin-top: 8px; }}
  summary {{
    font-size: 12px;
    color: var(--accent);
    cursor: pointer;
    user-select: none;
  }}
  details ul {{ margin: 8px 0 0 18px; }}
  details li {{
    font-size: 12px;
    color: var(--text-dim);
    margin-bottom: 3px;
    font-family: var(--mono);
  }}

  /* ── app section ── */
  .app-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
  }}
  @media (max-width: 900px) {{
    .app-grid {{ grid-template-columns: 1fr; }}
    .stats-bar {{ padding: 16px 20px; }}
    .header {{ padding: 20px; }}
    main {{ padding: 20px; }}
    nav {{ padding: 0 16px; }}
  }}
  .app-column h3 {{
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin-bottom: 10px;
    padding: 6px 10px;
    border-radius: 4px;
  }}
  .app-column.allowed h3 {{ background: #14532d30; color: #4ade80; }}
  .app-column.blocked h3 {{ background: #450a0a30; color: #f87171; }}

  .lookup-note {{
    font-size: 11px;
    color: var(--text-dim);
    margin-bottom: 8px;
    font-style: italic;
  }}
  .category-block {{ margin-bottom: 8px; }}

  /* ── footer ── */
  footer {{
    border-top: 1px solid var(--border);
    padding: 16px 40px;
    color: var(--text-dim);
    font-size: 11px;
    font-family: var(--mono);
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div>
      <h1>📋 MDM Profile Analysis</h1>
      <div class="subtitle">{esc(profile_path)}</div>
    </div>
    <div class="report-time">Generated {now}</div>
  </div>
  <div class="meta-chips">
    <div class="chip"><strong>Profile:</strong> {profile_name}</div>
    {"<div class='chip'><strong>Org:</strong> " + profile_org + "</div>" if profile_org else ""}
    {"<div class='chip'><strong>Desc:</strong> " + profile_desc + "</div>" if profile_desc else ""}
    <div class="chip"><strong>UUID:</strong> {profile_uuid}</div>
    <div class="chip"><strong>RemovalDisallowed:</strong> {esc(str(removal_flag))}</div>
  </div>
</div>

{removal_warning}

<div class="stats-bar">
  {stat_box("Deprecated Keys", total_deprecated, "#6366f1")}
  {stat_box("Insecure Configs", total_insecure, "#ef4444")}
  {stat_box("Conflicts", total_conflicts, "#f97316")}
  {stat_box("Allowed Apps", len(allowed_apps), "#22c55e")}
  {stat_box("Blocked Apps", len(blocked_apps), "#ef4444")}
</div>
<div class="sev-row">
  {"".join(
    f'<span class="sev-item" style="background:{SEV_COLOUR[s][1]};color:{SEV_COLOUR[s][0]}">'
    f'{s}: {sev_counts[s]}</span>'
    for s in ["CRITICAL","HIGH","MEDIUM","LOW"] if sev_counts[s] > 0
  )}
</div>

<nav>
  <a href="#deprecated">Deprecated ({total_deprecated})</a>
  <a href="#insecure">Insecure Configs ({total_insecure})</a>
  <a href="#conflicts">Conflicts ({total_conflicts})</a>
  <a href="#apps">Apps</a>
</nav>

<main>

  <!-- ── DEPRECATED ── -->
  <section id="deprecated">
    <h2>⚠️ Deprecated Restrictions <span class="count-badge">{total_deprecated}</span></h2>
    <p style="color:var(--text-dim);font-size:13px;margin-bottom:14px;">
      These keys are present in the profile but deprecated by Apple. They may be
      silently ignored on newer iOS versions. Review and replace with current equivalents.
    </p>
    <table>
      <thead><tr>
        <th>Key</th>
        <th>Category</th>
        <th style="width:70px">Value</th>
        <th style="width:90px">Dep. Since</th>
        <th>Replacement / Note</th>
      </tr></thead>
      <tbody>{dep_rows}</tbody>
    </table>
  </section>

  <!-- ── INSECURE ── -->
  <section id="insecure">
    <h2>🔒 Insecure Configurations <span class="count-badge">{total_insecure}</span></h2>
    <p style="color:var(--text-dim);font-size:13px;margin-bottom:6px;">
      Grouped by category. Deprecated keys are excluded (see above).
    </p>
    {insecure_html}
  </section>

  <!-- ── CONFLICTS ── -->
  <section id="conflicts">
    <h2>⚡ Conflicting Configurations <span class="count-badge">{total_conflicts}</span></h2>
    <p style="color:var(--text-dim);font-size:13px;margin-bottom:14px;">
      Combinations of settings that contradict each other or create unintended gaps.
    </p>
    {conflict_rows}
  </section>

  <!-- ── APPS ── -->
  <section id="apps">
    <h2>📦 Application Lists</h2>
    <div class="app-grid">
      <div class="app-column allowed">
        <h3>✅ Allowed Apps ({len(allowed_apps)})</h3>
        {allowed_table}
      </div>
      <div class="app-column blocked">
        <h3>🚫 Blocked Apps ({len(blocked_apps)})</h3>
        {blocked_table}
      </div>
    </div>
  </section>

</main>

<footer>
  MDM Profile Analyser · Reference: restriction_reference.yaml ·
  Apple MDM documentation captured 2026-03-24 ·
  This tool is a decision-support aid — all findings require human review.
</footer>

</body>
</html>"""
    return html


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyse an Apple MDM restrictions profile and produce an HTML report."
    )
    parser.add_argument("profile",   help="Path to the .xml/.mobileconfig/.plist profile")
    parser.add_argument("--ref",     default=str(DEFAULT_REF),
                        help="Path to restriction_reference.yaml (default: same dir as script)")
    parser.add_argument("--out",     default=None,
                        help="Output HTML path (default: <profile_name>_report.html)")
    parser.add_argument("--no-lookup", action="store_true",
                        help="Skip App Store bundle ID name lookups")
    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.profile):
        sys.exit(f"Error: Profile not found: {args.profile}")
    if not os.path.exists(args.ref):
        sys.exit(f"Error: Reference file not found: {args.ref}")
    if not HAS_REQUESTS and not args.no_lookup:
        print("Warning: 'requests' not installed — skipping App Store lookups. "
              "Install with: pip install requests", file=sys.stderr)
        args.no_lookup = True

    # Output path
    if args.out:
        out_path = args.out
    else:
        stem = Path(args.profile).stem
        out_path = str(Path(args.profile).parent / f"{stem}_report.html")

    print(f"[*] Loading profile:   {args.profile}")
    profile_data = load_profile(args.profile)
    restrictions, meta = extract_restrictions(profile_data)
    print(f"    Profile:           {meta['PayloadDisplayName']}")
    print(f"    Restrictions keys: {len(restrictions)}")

    print(f"[*] Loading reference: {args.ref}")
    ref, rules = load_reference(args.ref)
    print(f"    Reference keys:    {len(ref)}  |  Conflict rules: {len(rules)}")

    print("[*] Analysing deprecated keys...")
    deprecated = analyse_deprecated(restrictions, ref)
    print(f"    Found: {len(deprecated)}")

    print("[*] Analysing insecure configurations...")
    insecure = analyse_insecure(restrictions, ref)
    total_insecure = sum(len(v) for v in insecure.values())
    print(f"    Found: {total_insecure}")

    print("[*] Checking for conflicts...")
    conflicts = analyse_conflicts(restrictions, rules)
    print(f"    Found: {len(conflicts)}")

    do_lookup = not args.no_lookup
    if do_lookup:
        print("[*] Resolving app bundle IDs via App Store API...")
    else:
        print("[*] Skipping App Store lookup (--no-lookup)")

    allowed_apps, blocked_apps = analyse_apps(restrictions, do_lookup)
    print(f"    Allowed: {len(allowed_apps)}  |  Blocked: {len(blocked_apps)}")

    print(f"[*] Building HTML report...")
    html = build_html(
        meta, deprecated, insecure, conflicts,
        allowed_apps, blocked_apps, args.profile, do_lookup
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Report written to: {out_path}")
    print(f"\n   Summary:")
    print(f"   Deprecated keys  : {len(deprecated)}")
    print(f"   Insecure configs : {total_insecure}")
    print(f"   Conflicts        : {len(conflicts)}")
    print(f"   Allowed apps     : {len(allowed_apps)}")
    print(f"   Blocked apps     : {len(blocked_apps)}")


if __name__ == "__main__":
    main()
