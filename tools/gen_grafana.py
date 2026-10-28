"""Generate grafana/dyode-overview.json (Grafana 10/11, schemaVersion 39)."""
import json, sys
DS = {"type": "prometheus", "uid": "${datasource}"}
panels = []
pid = [0]
def P(kind, title, x, y, w, h, targets, **extra):
    pid[0] += 1
    p = {"id": pid[0], "type": kind, "title": title, "datasource": DS,
         "gridPos": {"x": x, "y": y, "w": w, "h": h},
         "targets": [dict(refId=chr(65 + i), datasource=DS, expr=e, legendFormat=l, **({"instant": True, "format": "table"} if kind == "table" else {}))
                     for i, (e, l) in enumerate(targets)]}
    p.update(extra)
    panels.append(p)
def row(title, y):
    pid[0] += 1
    panels.append({"id": pid[0], "type": "row", "title": title, "collapsed": False,
                   "gridPos": {"x": 0, "y": y, "w": 24, "h": 1}, "panels": []})
sel = 'job="$job", instance=~"$instance"'
thr = lambda steps: {"mode": "absolute", "steps": steps}
g, r, o = "green", "red", "orange"

row("Link", 0)
P("stat", "Input box status age", 0, 1, 6, 4,
  [(f'dyode_status_age_seconds{{side="in", {sel}}}', "{{instance}}")],
  description="Seconds since the input box's status arrived through the diode. Over 30 s: input box, diode or link down.",
  fieldConfig={"defaults": {"unit": "s", "decimals": 0, "thresholds": thr([{"color": g, "value": None}, {"color": o, "value": 15}, {"color": r, "value": 30}])}, "overrides": []},
  options={"colorMode": "background", "graphMode": "area", "reduceOptions": {"calcs": ["lastNotNull"]}})
P("stat", "Configurations match", 6, 1, 6, 4,
  [(f'dyode_config_match{{{sel}}}', "{{instance}}")],
  description="1 when both boxes run the same transport configuration (lidi parameters and modules).",
  fieldConfig={"defaults": {"mappings": [{"type": "value", "options": {"0": {"text": "DIFFERENT", "color": r}, "1": {"text": "same", "color": g}}}],
                            "thresholds": thr([{"color": r, "value": None}, {"color": g, "value": 1}])}, "overrides": []},
  options={"colorMode": "background", "graphMode": "none", "reduceOptions": {"calcs": ["lastNotNull"]}})
P("stat", "Transfers aborted (24 h)", 12, 1, 6, 4,
  [(f'increase(dyode_counter_total{{side="out", counter="lidi_transfers_aborted", {sel}}}[24h])', "{{instance}}")],
  description="lidi transfers aborted because blocks were lost in the diode.",
  fieldConfig={"defaults": {"decimals": 0, "thresholds": thr([{"color": g, "value": None}, {"color": o, "value": 1}])}, "overrides": []},
  options={"colorMode": "background", "graphMode": "none", "reduceOptions": {"calcs": ["lastNotNull"]}})
P("stat", "Versions", 18, 1, 6, 4,
  [(f'dyode_info{{{sel}}}', "{{side}}: {{version}}")],
  options={"colorMode": "none", "graphMode": "none", "textMode": "name", "reduceOptions": {"calcs": ["lastNotNull"]}})
P("timeseries", "Input box status age", 0, 5, 24, 6,
  [(f'dyode_status_age_seconds{{side="in", {sel}}}', "status age")],
  fieldConfig={"defaults": {"unit": "s", "custom": {"thresholdsStyle": {"mode": "line"}},
                            "thresholds": thr([{"color": g, "value": None}, {"color": r, "value": 30}])}, "overrides": []})

row("Throughput", 11)
P("timeseries", "File bytes per second", 0, 12, 12, 8,
  [(f'sum by (side, module) (rate(dyode_bytes_total{{{sel}}}[5m]))', "{{side}} {{module}}")],
  fieldConfig={"defaults": {"unit": "Bps"}, "overrides": []})
P("timeseries", "Files per minute", 12, 12, 12, 8,
  [(f'sum by (side, module, event) (rate(dyode_events_total{{event=~"file_sent|file_stored|file_rejected|file_missing|file_failed", {sel}}}[5m])) * 60', "{{side}} {{module}} {{event}}")],
  fieldConfig={"defaults": {"unit": "short"}, "overrides": []})

row("Modules", 20)
P("table", "Modules", 0, 21, 12, 8,
  [(f'dyode_module_up{{{sel}}}', ""), (f'dyode_module_restarts_total{{{sel}}}', "")],
  transformations=[{"id": "merge", "options": {}},
                   {"id": "organize", "options": {"excludeByName": {"Time": True, "__name__": True, "job": True, "instance": True, "diode": True},
                                                  "renameByName": {"Value #A": "up", "Value #B": "restarts"}}}],
  fieldConfig={"defaults": {}, "overrides": [{"matcher": {"id": "byName", "options": "up"},
               "properties": [{"id": "mappings", "value": [{"type": "value", "options": {"0": {"text": "restarting", "color": r}, "1": {"text": "running", "color": g}}}]},
                              {"id": "custom.cellOptions", "value": {"type": "color-background"}}]}]})
P("timeseries", "Events (rate, per minute)", 12, 21, 12, 8,
  [(f'sum by (side, module, event) (rate(dyode_events_total{{{sel}}}[5m])) * 60', "{{side}} {{module}} {{event}}")],
  fieldConfig={"defaults": {"unit": "short"}, "overrides": []})
P("bargauge", "Free space", 0, 29, 24, 6,
  [(f'dyode_free_bytes{{{sel}}}', "{{side}} {{module}} {{dir}}")],
  fieldConfig={"defaults": {"unit": "bytes", "thresholds": thr([{"color": r, "value": None}, {"color": o, "value": 5e9}, {"color": g, "value": 2e10}])}, "overrides": []},
  options={"orientation": "horizontal", "displayMode": "gradient", "reduceOptions": {"calcs": ["lastNotNull"]}})

row("API", 35)
P("timeseries", "Refused API requests (per minute)", 0, 36, 24, 6,
  [(f'sum by (side) (rate(dyode_counter_total{{counter="api_refused", {sel}}}[5m])) * 60', "{{side}}")],
  fieldConfig={"defaults": {"unit": "short"}, "overrides": []})

dash = {

    "__requires": [{"type": "grafana", "id": "grafana", "name": "Grafana", "version": "10.0.0"},
                   {"type": "datasource", "id": "prometheus", "name": "Prometheus", "version": "1.0.0"}],
    "title": "DYODE overview",
    "uid": "dyode-overview",
    "description": "Both DYODE boxes, from the output box's /metrics (nc-intezra/dyode_monitoring).",
    "tags": ["dyode", "diode"],
    "timezone": "browser",
    "schemaVersion": 39,
    "version": 1,
    "refresh": "30s",
    "time": {"from": "now-6h", "to": "now"},
    "editable": True,
    "templating": {"list": [
        {"name": "datasource", "label": "Prometheus", "type": "datasource", "query": "prometheus", "current": {}, "hide": 0},
        {"name": "job", "label": "Job", "type": "query", "datasource": DS, "query": {"query": "label_values(dyode_info, job)", "refId": "job"},
         "definition": "label_values(dyode_info, job)", "refresh": 1, "current": {}, "hide": 0},
        {"name": "instance", "label": "Output box", "type": "query", "datasource": DS,
         "query": {"query": 'label_values(dyode_info{job="$job"}, instance)', "refId": "inst"},
         "definition": 'label_values(dyode_info{job="$job"}, instance)', "refresh": 1, "includeAll": True, "multi": True, "current": {}, "hide": 0},
    ]},
    "annotations": {"list": []},
    "panels": panels,
}
json.dump(dash, open(sys.argv[1], "w"), indent=2)
print(len(panels), "panels")
