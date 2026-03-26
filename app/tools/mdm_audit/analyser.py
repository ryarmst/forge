"""
MDM Profile Analyser — core analysis logic.

All functions operate on in-memory data structures (no file I/O).
"""

import plistlib
from collections import defaultdict
from datetime import datetime

import yaml


def parse_profile(raw_bytes):
    """Parse a .mobileconfig / .plist / .xml file from raw bytes."""
    return plistlib.loads(raw_bytes)


def extract_restrictions(profile):
    """Return (restrictions_dict, metadata_dict) from a parsed profile."""
    meta = {
        "PayloadDisplayName": profile.get("PayloadDisplayName", "Unknown"),
        "PayloadDescription": profile.get("PayloadDescription", ""),
        "PayloadOrganization": profile.get("PayloadOrganization", ""),
        "PayloadUUID": profile.get("PayloadUUID", ""),
        "PayloadRemovalDisallowed": profile.get("PayloadRemovalDisallowed", None),
    }

    restrictions = {}
    if meta["PayloadRemovalDisallowed"] is not None:
        restrictions["PayloadRemovalDisallowed"] = meta["PayloadRemovalDisallowed"]

    for payload in profile.get("PayloadContent", []):
        if payload.get("PayloadType") == "com.apple.applicationaccess":
            for k, v in payload.items():
                if not k.startswith("Payload"):
                    restrictions[k] = v
    return restrictions, meta


def load_reference_yaml(yaml_text):
    """Parse reference YAML text. Returns (restrictions_by_key, conflict_rules)."""
    data = yaml.safe_load(yaml_text)
    by_key = {r["key"]: r for r in data.get("restrictions", [])}
    rules = data.get("conflict_rules", [])
    return by_key, rules


def analyse_deprecated(restrictions, ref):
    findings = []
    for key, value in restrictions.items():
        r = ref.get(key)
        if r and r.get("deprecated"):
            findings.append({
                "key": key,
                "value": value,
                "since": r.get("deprecated_since", "unknown"),
                "note": r.get("deprecated_note", ""),
                "category": r.get("category", ""),
            })
    return sorted(findings, key=lambda x: x["category"])


def analyse_insecure(restrictions, ref):
    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    by_category = defaultdict(list)

    for key, value in restrictions.items():
        r = ref.get(key)
        if not r or r.get("deprecated"):
            continue
        insecure_val = r.get("insecure_if_value")
        if insecure_val is None:
            continue
        if value == insecure_val or str(value) == str(insecure_val):
            by_category[r.get("category", "Uncategorized")].append({
                "key": key,
                "value": value,
                "severity": r.get("insecure_severity", "LOW"),
                "note": r.get("insecure_note", ""),
            })

    delay_key = "enforcedSoftwareUpdateDelay"
    if delay_key in restrictions:
        r = ref.get(delay_key)
        if r and not r.get("deprecated"):
            val = restrictions[delay_key]
            if isinstance(val, int) and val >= 60:
                by_category[r.get("category", "Device")].append({
                    "key": delay_key,
                    "value": val,
                    "severity": "HIGH",
                    "note": r.get("insecure_note", f"Update delay of {val} days is excessive."),
                })

    for cat in by_category:
        by_category[cat].sort(key=lambda x: sev_order.get(x["severity"], 9))
    return dict(by_category)


def analyse_conflicts(restrictions, rules):
    triggered = []
    for rule in rules:
        conditions = rule.get("conditions", [])
        if not conditions:
            continue
        all_match = True
        for cond in conditions:
            key = cond["key"]
            op = cond.get("op", "eq")
            val = cond["value"]
            actual = restrictions.get(key, "__NOT_PRESENT__")

            if actual == "__NOT_PRESENT__":
                if key == "PayloadRemovalDisallowed":
                    actual = False
                else:
                    all_match = False
                    break

            if op == "eq" and actual != val:
                all_match = False
                break
            if op == "ne" and actual == val:
                all_match = False
                break
            if op == "gt" and not (isinstance(actual, (int, float)) and actual > val):
                all_match = False
                break
            if op == "lt" and not (isinstance(actual, (int, float)) and actual < val):
                all_match = False
                break

        if all_match:
            triggered.append(rule)

    sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(triggered, key=lambda x: sev_order.get(x.get("severity", "LOW"), 9))


def extract_apps(restrictions):
    """Return (allowed_ids, blocked_ids) as lists of bundle ID strings."""
    return (
        restrictions.get("allowListedAppBundleIDs", []),
        restrictions.get("blockedAppBundleIDs", []),
    )


SEV_COLOUR = {
    "CRITICAL": ("#7f1d1d", "#fee2e2"),
    "HIGH": ("#7c2d12", "#ffedd5"),
    "MEDIUM": ("#78350f", "#fef9c3"),
    "LOW": ("#1e3a5f", "#dbeafe"),
}


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _sev_badge(severity):
    fg, bg = SEV_COLOUR.get(severity, ("#374151", "#f3f4f6"))
    return f'<span style="display:inline-block;font-size:10px;font-weight:700;font-family:monospace;padding:2px 7px;border-radius:3px;letter-spacing:0.5px;text-transform:uppercase;background:{bg};color:{fg}">{severity}</span>'


def _bool_pill(v):
    if v is True:
        return '<span style="display:inline-block;font-family:monospace;font-size:11px;padding:2px 7px;border-radius:10px;font-weight:600;background:#14532d;color:#86efac">true</span>'
    if v is False:
        return '<span style="display:inline-block;font-family:monospace;font-size:11px;padding:2px 7px;border-radius:10px;font-weight:600;background:#450a0a;color:#fca5a5">false</span>'
    return f'<code>{_esc(v)}</code>'


def build_report_html(meta, deprecated, insecure, conflicts, allowed_ids, blocked_ids, filename):
    """Generate a self-contained HTML report string."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    profile_name = _esc(meta.get("PayloadDisplayName", "Unknown"))
    profile_desc = _esc(meta.get("PayloadDescription", ""))
    profile_org = _esc(meta.get("PayloadOrganization", ""))
    profile_uuid = _esc(meta.get("PayloadUUID", ""))
    removal_flag = meta.get("PayloadRemovalDisallowed")

    total_deprecated = len(deprecated)
    total_insecure = sum(len(v) for v in insecure.values())
    total_conflicts = len(conflicts)

    sev_counts = defaultdict(int)
    for findings in insecure.values():
        for f in findings:
            sev_counts[f["severity"]] += 1
    for f in conflicts:
        sev_counts[f.get("severity", "LOW")] += 1

    def stat_box(label, value, colour):
        return f'<div style="background:#222636;border-radius:6px;padding:12px 20px;min-width:130px;flex:1;border-left:4px solid {colour}"><div style="font-size:28px;font-weight:600;font-family:monospace;color:#e2e4ef;line-height:1">{value}</div><div style="font-size:11px;color:#8b90a8;text-transform:uppercase;letter-spacing:0.6px;margin-top:4px">{label}</div></div>'

    dep_rows = ""
    if deprecated:
        for d in deprecated:
            dep_rows += f'<tr><td><code>{_esc(d["key"])}</code></td><td>{_esc(d["category"])}</td><td>{_bool_pill(d["value"])}</td><td>{_esc(d["since"])}</td><td style="color:#a9afc8;font-size:12.5px">{_esc(d["note"])}</td></tr>'
    else:
        dep_rows = '<tr><td colspan="5" style="color:#8b90a8;font-size:13px;padding:16px 0;text-align:center">No deprecated restrictions found.</td></tr>'

    insecure_html = ""
    if insecure:
        for cat, findings in sorted(insecure.items()):
            rows = ""
            for f in findings:
                rows += f'<tr><td>{_sev_badge(f["severity"])}</td><td><code>{_esc(f["key"])}</code></td><td>{_bool_pill(f["value"])}</td><td style="color:#a9afc8;font-size:12.5px">{_esc(f["note"])}</td></tr>'
            insecure_html += f'<h3 style="font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;color:#4f8ef7;margin:24px 0 10px">{_esc(cat)}</h3><table><thead><tr><th style="width:100px">Severity</th><th>Key</th><th style="width:80px">Value</th><th>Finding</th></tr></thead><tbody>{rows}</tbody></table>'
    else:
        insecure_html = '<p style="color:#8b90a8;font-size:13px;padding:16px 0">No insecure configurations detected.</p>'

    conflict_html = ""
    if conflicts:
        for c in conflicts:
            fg, _ = SEV_COLOUR.get(c.get("severity", "LOW"), ("#374151", "#f3f4f6"))
            cond_list = "".join(
                f'<li><code>{_esc(x["key"])}</code> {_esc(x.get("op", "eq"))} <code>{_esc(x["value"])}</code></li>'
                for x in c.get("conditions", [])
            )
            conflict_html += f'<div style="background:#1a1d27;border-radius:6px;padding:16px 18px;margin-bottom:12px;border-left:4px solid {fg}"><div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:8px">{_sev_badge(c.get("severity","LOW"))} <span style="font-family:monospace;font-size:11px;color:#8b90a8">{_esc(c.get("id",""))}</span> <strong>{_esc(c.get("description",""))}</strong></div><p style="color:#a9afc8;font-size:12.5px">{_esc(c.get("note",""))}</p><details style="margin-top:8px"><summary style="font-size:12px;color:#4f8ef7;cursor:pointer">Triggering conditions</summary><ul style="margin:8px 0 0 18px">{cond_list}</ul></details></div>'
    else:
        conflict_html = '<p style="color:#8b90a8;font-size:13px;padding:16px 0">No conflicting configurations detected.</p>'

    def app_table(ids, label):
        if not ids:
            return f'<p style="color:#8b90a8;font-size:13px;padding:8px 0">No {label.lower()} apps defined.</p>'
        rows = "".join(f'<tr><td><code>{_esc(bid)}</code></td></tr>' for bid in sorted(ids))
        return f'<table><thead><tr><th>Bundle ID</th></tr></thead><tbody>{rows}</tbody></table>'

    removal_warning = ""
    if removal_flag is False or removal_flag is None:
        removal_warning = '<div style="background:#3b0a0a;border:1px solid #7f1d1d;border-radius:6px;padding:14px 18px;margin:24px 0 0;color:#fca5a5;font-size:13px;line-height:1.5">&#9888;&#65039; <strong>PayloadRemovalDisallowed is false or absent.</strong> This profile can be removed by the user without MDM authorization, rendering all restrictions ineffective.</div>'

    sev_row_items = "".join(
        f'<span style="font-size:12px;font-family:monospace;padding:2px 8px;border-radius:3px;background:{SEV_COLOUR[s][1]};color:{SEV_COLOUR[s][0]}">{s}: {sev_counts[s]}</span>'
        for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"] if sev_counts[s] > 0
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MDM Profile Analysis &ndash; {profile_name}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap');
  :root {{ --bg:#0f1117; --surface:#1a1d27; --surface2:#222636; --border:#2e3347; --text:#e2e4ef; --dim:#8b90a8; --accent:#4f8ef7; --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:var(--sans); background:var(--bg); color:var(--text); font-size:14px; line-height:1.6; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; margin-bottom:8px; }}
  th {{ background:var(--surface2); color:var(--dim); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:0.6px; padding:9px 14px; text-align:left; border:1px solid var(--border); }}
  td {{ padding:9px 14px; border:1px solid var(--border); vertical-align:top; }}
  tr:nth-child(even) td {{ background:#161921; }}
  tr:nth-child(odd) td {{ background:var(--surface); }}
  tr:hover td {{ background:#1e2338; }}
  code {{ font-family:var(--mono); font-size:12px; background:#1e2338; padding:1px 5px; border-radius:3px; color:#93c5fd; white-space:nowrap; }}
  section {{ margin-bottom:48px; }}
  h2 {{ font-size:17px; font-weight:600; color:#c9d8ff; margin-bottom:16px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
  details ul {{ margin:8px 0 0 18px; }} details li {{ font-size:12px; color:var(--dim); margin-bottom:3px; font-family:var(--mono); }}
</style>
</head>
<body>
<div style="background:linear-gradient(135deg,#0e1628 0%,#1a2744 100%);border-bottom:1px solid #2a3a60;padding:32px 40px 24px">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px">
    <div><h1 style="font-size:22px;font-weight:600;letter-spacing:-0.3px;color:#c9d8ff">MDM Profile Analysis</h1><div style="font-size:12px;color:var(--dim);margin-top:4px;font-family:var(--mono)">{_esc(filename)}</div></div>
    <div style="font-size:11px;color:var(--dim);font-family:var(--mono);white-space:nowrap">Generated {now}</div>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:18px">
    <div style="background:#1e2d50;border:1px solid #2a3f6a;border-radius:4px;padding:3px 10px;font-size:11px;font-family:var(--mono);color:#93a8d4"><strong style="color:#c9d8ff">Profile:</strong> {profile_name}</div>
    {"<div style='background:#1e2d50;border:1px solid #2a3f6a;border-radius:4px;padding:3px 10px;font-size:11px;font-family:var(--mono);color:#93a8d4'><strong style='color:#c9d8ff'>Org:</strong> " + profile_org + "</div>" if profile_org else ""}
    <div style="background:#1e2d50;border:1px solid #2a3f6a;border-radius:4px;padding:3px 10px;font-size:11px;font-family:var(--mono);color:#93a8d4"><strong style="color:#c9d8ff">UUID:</strong> {profile_uuid}</div>
    <div style="background:#1e2d50;border:1px solid #2a3f6a;border-radius:4px;padding:3px 10px;font-size:11px;font-family:var(--mono);color:#93a8d4"><strong style="color:#c9d8ff">RemovalDisallowed:</strong> {_esc(str(removal_flag))}</div>
  </div>
  {removal_warning}
</div>

<div style="display:flex;gap:16px;flex-wrap:wrap;padding:20px 40px;background:var(--surface);border-bottom:1px solid var(--border)">
  {stat_box("Deprecated Keys", total_deprecated, "#6366f1")}
  {stat_box("Insecure Configs", total_insecure, "#ef4444")}
  {stat_box("Conflicts", total_conflicts, "#f97316")}
  {stat_box("Allowed Apps", len(allowed_ids), "#22c55e")}
  {stat_box("Blocked Apps", len(blocked_ids), "#ef4444")}
</div>
<div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:8px 40px;background:var(--surface);border-bottom:1px solid var(--border)">{sev_row_items}</div>

<main style="padding:32px 40px;max-width:1300px">

<section>
  <h2>Deprecated Restrictions ({total_deprecated})</h2>
  <table><thead><tr><th>Key</th><th>Category</th><th style="width:70px">Value</th><th style="width:90px">Dep. Since</th><th>Replacement / Note</th></tr></thead><tbody>{dep_rows}</tbody></table>
</section>

<section>
  <h2>Insecure Configurations ({total_insecure})</h2>
  {insecure_html}
</section>

<section>
  <h2>Conflicting Configurations ({total_conflicts})</h2>
  {conflict_html}
</section>

<section>
  <h2>Application Lists</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:24px">
    <div><h3 style="font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px;padding:6px 10px;border-radius:4px;background:rgba(20,83,45,0.19);color:#4ade80">Allowed Apps ({len(allowed_ids)})</h3>{app_table(allowed_ids, "Allowed")}</div>
    <div><h3 style="font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;margin-bottom:10px;padding:6px 10px;border-radius:4px;background:rgba(69,10,10,0.19);color:#f87171">Blocked Apps ({len(blocked_ids)})</h3>{app_table(blocked_ids, "Blocked")}</div>
  </div>
</section>

</main>

<footer style="border-top:1px solid var(--border);padding:16px 40px;color:var(--dim);font-size:11px;font-family:var(--mono)">
  MDM Profile Auditor &middot; Forge &middot; This tool is a decision-support aid &mdash; all findings require human review.
</footer>
</body>
</html>"""
