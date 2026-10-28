"""Check that everything here parses and only uses what DYODE serves.

  python3 tools/check.py

- every YAML/JSON file parses;
- every dyode_* metric in the alert rules and the dashboard exists in
  DYODE's /metrics (examples/metrics.txt, captured from a real 2.1.0 run,
  plus the few families that only appear when known);
- every JSONPath field the Zabbix template reads exists in /v1/status
  (examples/status.json);
- the generated files match their generators (tools/gen_*.py).
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fail = []

def check(ok, msg):
    if not ok:
        fail.append(msg)

try:
    import yaml
except ImportError:
    sys.exit("needs PyYAML (pip install pyyaml)")

rules = yaml.safe_load((ROOT / "prometheus/rules/dyode.rules.yml").read_text())
yaml.safe_load((ROOT / "prometheus/scrape.yml").read_text())
dash = json.loads((ROOT / "grafana/dyode-overview.json").read_text())
zbx = yaml.safe_load((ROOT / "zabbix/dyode_by_http.yaml").read_text())
status = json.loads((ROOT / "examples/status.json").read_text())

# Families DYODE serves: those in the sample, and those that appear only
# when known (docs/API.md).
served = set(re.findall(r"^# HELP (dyode_\w+)", (ROOT / "examples/metrics.txt").read_text(), re.M))
served |= {"dyode_static_arp_ok", "dyode_config_match"}
for need in ["dyode_status_age_seconds", "dyode_status_received", "dyode_module_up", "dyode_events_total"]:
    check(need in served, f"examples/metrics.txt lacks {need}")

def metrics_in(expr):
    return set(re.findall(r"\b(dyode_\w+)", expr))

exprs = [r["expr"] for g in rules["groups"] for r in g["rules"]]
check(len(exprs) >= 10, "too few alert rules")
for r in (r for g in rules["groups"] for r in g["rules"]):
    check({"alert", "expr", "labels", "annotations"} <= r.keys(), f"rule {r.get('alert')} incomplete")
    check(r["labels"].get("severity") in {"critical", "warning", "info"}, f"rule {r['alert']}: severity")
    check(r["expr"].count("(") == r["expr"].count(")"), f"rule {r['alert']}: parentheses")
    check(r["expr"].count("{") == r["expr"].count("}"), f"rule {r['alert']}: braces")
for p in dash["panels"]:
    for t in p.get("targets", []):
        exprs.append(t["expr"])
for e in exprs:
    for m in metrics_in(e):
        check(m in served, f"{m} is not served by DYODE (in: {e})")

# Zabbix: the JSONPaths must lead somewhere in /v1/status.
tmpl = zbx["zabbix_export"]["templates"][0]
check(zbx["zabbix_export"]["version"] == "7.0", "Zabbix export version")
uuids = []
def walk(o):
    if isinstance(o, dict):
        if "uuid" in o:
            uuids.append(o["uuid"])
        for v in o.values():
            walk(v)
    elif isinstance(o, list):
        for v in o:
            walk(v)
walk(zbx)
check(len(uuids) == len(set(uuids)), "duplicate UUIDs in the Zabbix template")
check(all(re.fullmatch(r"[0-9a-f]{32}", u) for u in uuids), "UUIDs must be 32 hex digits")

def resolve(path, doc):
    """Follow a simple $.a.b.c path (filters stop the walk)."""
    cur = doc
    for part in path.lstrip("$.").split("."):
        if "[" in part or part.endswith("()"):
            return True
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    return True

keys = {i["key"] for i in tmpl["items"]}
for i in tmpl["items"]:
    for step in i.get("preprocessing", []):
        if step["type"] == "JSONPATH":
            p = step["parameters"][0]
            has_default = "error_handler" in step
            check(resolve(p, status) or has_default, f"item {i['key']}: {p} not in /v1/status")
    if i["type"] == "DEPENDENT":
        check(i["master_item"]["key"] in keys, f"item {i['key']}: master missing")
for rule in tmpl["discovery_rules"]:
    p = rule["preprocessing"][0]["parameters"][0]
    check(resolve(p, status), f"discovery {rule['key']}: {p} not in /v1/status")
    for proto in rule["item_prototypes"]:
        field = re.search(r"\]\.(\w+)", proto["preprocessing"][0]["parameters"][0])
        mod = (status["boxes"].get("out") or {}).get("modules", [{}])[0]
        if field and field.group(1) != "events":
            check(field.group(1) in mod, f"prototype {proto['key']}: no field {field.group(1)}")

# Generated files are up to date.
for gen, out in [("gen_grafana.py", "grafana/dyode-overview.json"), ("gen_zabbix.py", "zabbix/dyode_by_http.yaml")]:
    with tempfile.NamedTemporaryFile(suffix=Path(out).suffix) as tmp:
        subprocess.run([sys.executable, str(ROOT / "tools" / gen), tmp.name], check=True, capture_output=True)
        check(Path(tmp.name).read_text() == (ROOT / out).read_text(), f"{out} is stale: run tools/{gen} {out}")

if fail:
    print("\n".join("FAIL: " + f for f in fail))
    sys.exit(1)
print(f"ok: {len(exprs)} expressions, {len(uuids)} Zabbix objects, {len(served)} metric families")
