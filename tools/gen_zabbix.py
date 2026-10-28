"""Generate zabbix/dyode_by_http.yaml: a Zabbix 7.0 template for the DYODE
output box's API (/v1/status).  UUIDs are derived from names, so
regenerating gives the same template."""
import sys, uuid, yaml

NS = uuid.UUID("6f1c2a52-6b1e-4c43-9d2b-2d1f0a7c0d11")
def U(name): return uuid.uuid5(NS, name).hex
T = "DYODE by HTTP"

def dep(name, key, path, value_type="FLOAT", units="", error_value=None, triggers=None, desc="", tags=None, extra_pre=None):
    pre = [{"type": "JSONPATH", "parameters": [path]}]
    if error_value is not None:
        pre[0].update({"error_handler": "CUSTOM_VALUE", "error_handler_params": error_value})
    if extra_pre: pre += extra_pre
    it = {"uuid": U(key), "name": name, "type": "DEPENDENT", "key": key, "delay": "0",
          "value_type": value_type, "description": desc, "preprocessing": pre,
          "master_item": {"key": "dyode.status.get"},
          "tags": tags or [{"tag": "component", "value": "dyode"}]}
    if units: it["units"] = units
    if value_type in ("CHAR", "TEXT"): it["trends"] = "0"
    if triggers: it["triggers"] = triggers
    return it

def trig(name, expr, prio, desc="", recovery=None):
    t = {"uuid": U("trig:" + name), "expression": expr, "name": name, "priority": prio, "description": desc,
         "tags": [{"tag": "scope", "value": "availability"}]}
    if recovery:
        t["recovery_mode"] = "RECOVERY_EXPRESSION"; t["recovery_expression"] = recovery
    return t

items = [
    {"uuid": U("dyode.status.get"), "name": "DYODE: Get status", "type": "HTTP_AGENT", "key": "dyode.status.get",
     "delay": "{$DYODE.INTERVAL}", "history": "0", "value_type": "TEXT", "trends": "0",
     "url": "{$DYODE.URL}/v1/status", "timeout": "10s",
     "headers": [{"name": "Authorization", "value": "Bearer {$DYODE.TOKEN}"}],
     "verify_peer": "YES", "verify_host": "YES",
     "description": "/v1/status of the DYODE output box: both boxes (the input box as last received through the diode) and warnings.",
     "tags": [{"tag": "component", "value": "raw"}],
     "triggers": [trig("DYODE: output box API not answering", f"nodata(/{T}/dyode.status.get,{{$DYODE.NODATA}})=1", "HIGH",
                       "No /v1/status for {$DYODE.NODATA}: DYODE stopped, the box is down, or the token or certificate changed.")]},
    dep("DYODE: Input box status age", "dyode.in.status_age", "$.boxes.in.status_age_s", units="s", error_value="-1",
        desc="Seconds since the input box's status arrived through the diode; -1 when none has arrived yet.",
        triggers=[trig("DYODE: no status from the input box",
                       f"last(/{T}/dyode.in.status_age)>{{$DYODE.IN.SILENT}} or last(/{T}/dyode.in.status_age)<0", "HIGH",
                       "The input box, its diode NIC, the diode or the output box's receiver has failed: nothing is crossing.")]),
    dep("DYODE: Warnings", "dyode.warnings", "$.warnings", value_type="TEXT",
        desc="Warnings from the output box, e.g. a silent input box or differing configurations.",
        extra_pre=[{"type": "JAVASCRIPT", "parameters": ["var w = JSON.parse(value); return w.length ? w.join('\\n') : '';"]}]),
    dep("DYODE: Output box transport hash", "dyode.out.hash", "$.boxes.out.transport_hash", value_type="CHAR",
        extra_pre=[{"type": "DISCARD_UNCHANGED_HEARTBEAT", "parameters": ["1h"]}]),
    dep("DYODE: Input box transport hash", "dyode.in.hash", "$.boxes.in.transport_hash", value_type="CHAR", error_value="unknown",
        extra_pre=[{"type": "DISCARD_UNCHANGED_HEARTBEAT", "parameters": ["1h"]}],
        triggers=[trig("DYODE: the boxes run different configurations",
                       f"last(/{T}/dyode.in.hash)<>last(/{T}/dyode.out.hash) and last(/{T}/dyode.in.hash)<>\"unknown\"", "HIGH",
                       "Copy the same config.yaml to both boxes.")]),
    dep("DYODE: Output box version", "dyode.out.version", "$.boxes.out.version", value_type="CHAR",
        extra_pre=[{"type": "DISCARD_UNCHANGED_HEARTBEAT", "parameters": ["1d"]}]),
    dep("DYODE: Output box uptime", "dyode.out.uptime", "$.boxes.out.uptime_s", units="uptime", value_type="UNSIGNED"),
    dep("DYODE: Input box uptime", "dyode.in.uptime", "$.boxes.in.uptime_s", units="uptime", value_type="UNSIGNED", error_value="0"),
    dep("DYODE: Transfers aborted by lidi", "dyode.out.aborted", "$.boxes.out.counters.lidi_transfers_aborted", value_type="UNSIGNED",
        error_value="0", extra_pre=[{"type": "SIMPLE_CHANGE", "parameters": [""]}],
        desc="Transfers aborted since the last poll (blocks lost in the diode).",
        triggers=[trig("DYODE: lidi aborted transfers", f"sum(/{T}/dyode.out.aborted,15m)>0", "WARNING",
                       "Lost files are named in file_missing events; re-send them from .dyode_sent on the input box.")]),
    dep("DYODE: Input box static ARP entry", "dyode.in.arp", "$.boxes.in.static_arp_ok", value_type="UNSIGNED", error_value="1",
        extra_pre=[{"type": "BOOL_TO_DECIMAL", "parameters": [""]}],
        triggers=[trig("DYODE: input box static ARP entry missing", f"last(/{T}/dyode.in.arp)=0", "HIGH",
                       "Without it the input box's kernel drops everything sent to the output box.")]),
]

def module_rule(side):
    label = "input" if side == "in" else "output"
    key = f"dyode.modules.{side}"
    m = "{#MODULE}"
    sel = f"$.boxes.{side}.modules[?(@.name=='{m}')]"
    def proto(name, k, path, vt="UNSIGNED", units="", error_value="0", extra=None, triggers=None, desc=""):
        pre = [{"type": "JSONPATH", "parameters": [path], "error_handler": "CUSTOM_VALUE", "error_handler_params": error_value}]
        if extra: pre += extra
        p = {"uuid": U(f"{side}:{k}"), "name": name, "type": "DEPENDENT", "key": k, "delay": "0", "value_type": vt,
             "description": desc, "preprocessing": pre, "master_item": {"key": "dyode.status.get"},
             "tags": [{"tag": "component", "value": "module"}, {"tag": "module", "value": m}, {"tag": "side", "value": side}]}
        if units: p["units"] = units
        if vt in ("CHAR", "TEXT"): p["trends"] = "0"
        if triggers: p["trigger_prototypes"] = triggers
        return p
    def tp(name, expr, prio, desc=""):
        return {"uuid": U(f"{side}:tp:{name}"), "expression": expr, "name": name, "priority": prio, "description": desc}
    protos = [
        proto(f"DYODE {label} module {m}: state", f"dyode.module.state[{side},{m}]", f"{sel}.state.first()", vt="CHAR", error_value="unknown",
              triggers=[tp(f"DYODE {label} module {m} is not running",
                           f"last(/{T}/dyode.module.state[{side},{m}])=\"restarting\"", "AVERAGE")]),
        proto(f"DYODE {label} module {m}: restarts", f"dyode.module.restarts[{side},{m}]", f"{sel}.restarts.first()",
              triggers=[tp(f"DYODE {label} module {m} keeps restarting",
                           f"change(/{T}/dyode.module.restarts[{side},{m}])>0", "WARNING")]),
    ]
    if side == "out":
        protos += [
            proto(f"DYODE output module {m}: files rejected", f"dyode.module.rejected[{m}]", f"{sel}.events.file_rejected.first()",
                  extra=[{"type": "SIMPLE_CHANGE", "parameters": [""]}],
                  triggers=[tp(f"DYODE output module {m}: files rejected", f"sum(/{T}/dyode.module.rejected[{m}],15m)>0", "WARNING",
                               "Incomplete or not signed with the shared key; see transfer.jsonl.")]),
            proto(f"DYODE output module {m}: files missing", f"dyode.module.missing[{m}]", f"{sel}.events.file_missing.first()",
                  extra=[{"type": "SIMPLE_CHANGE", "parameters": [""]}],
                  triggers=[tp(f"DYODE output module {m}: files never arrived", f"sum(/{T}/dyode.module.missing[{m}],30m)>0", "WARNING",
                               "Re-send them from .dyode_sent on the input box.")]),
            proto(f"DYODE output module {m}: bytes stored per second", f"dyode.module.bytes[{side},{m}]", f"{sel}.bytes_stored.first()",
                  vt="FLOAT", units="Bps", extra=[{"type": "CHANGE_PER_SECOND", "parameters": [""]}]),
        ]
    else:
        protos += [
            proto(f"DYODE input module {m}: bytes sent per second", f"dyode.module.bytes[{side},{m}]", f"{sel}.bytes_sent.first()",
                  vt="FLOAT", units="Bps", extra=[{"type": "CHANGE_PER_SECOND", "parameters": [""]}]),
        ]
    return {"uuid": U(key), "name": f"DYODE: {label} box modules", "type": "DEPENDENT", "key": key, "delay": "0",
            "master_item": {"key": "dyode.status.get"},
            "lifetime": "7d",
            "preprocessing": [{"type": "JSONPATH", "parameters": [f"$.boxes.{side}.modules"],
                               "error_handler": "CUSTOM_VALUE", "error_handler_params": "[]"}],
            "lld_macro_paths": [{"lld_macro": "{#MODULE}", "path": "$.name"}, {"lld_macro": "{#TYPE}", "path": "$.type"}],
            "item_prototypes": protos}

template = {
    "uuid": U("template"), "template": T, "name": T,
    "description": "DYODE (nc-intezra/dyode_rust) 2.1.0+, through the OUTPUT box's local API (/v1/status).\n"
                   "Covers both boxes: the input box from the status it sends through the diode.\n"
                   "Set {$DYODE.URL} (https://ADDRESS:8443) and {$DYODE.TOKEN} (dyode api-token add zabbix).\n"
                   "The Zabbix server must trust the output box's certificate (its CA path), or set verify_peer off on the master item.\n"
                   "Generated by tools/gen_zabbix.py in nc-intezra/dyode_monitoring.",
    "vendor": {"name": "nc-intezra", "version": "7.0-1"},
    "groups": [{"name": "Templates/Applications"}],
    "items": items,
    "discovery_rules": [module_rule("in"), module_rule("out")],
    "tags": [{"tag": "class", "value": "software"}, {"tag": "target", "value": "dyode"}],
    "macros": [
        {"macro": "{$DYODE.URL}", "value": "https://192.168.50.4:8443", "description": "The output box's api.out.listen, with https://"},
        {"macro": "{$DYODE.TOKEN}", "type": "SECRET_TEXT", "description": "A read token from: sudo dyode api-token add zabbix"},
        {"macro": "{$DYODE.INTERVAL}", "value": "30s", "description": "How often /v1/status is read"},
        {"macro": "{$DYODE.NODATA}", "value": "3m", "description": "No answer for this long: API down"},
        {"macro": "{$DYODE.IN.SILENT}", "value": "30", "description": "Seconds without input box status before alerting"},
    ],
}
export = {"zabbix_export": {"version": "7.0",
                            "template_groups": [{"uuid": U("group"), "name": "Templates/Applications"}],
                            "templates": [template]}}
class D(yaml.SafeDumper): pass
D.ignore_aliases = lambda *a: True
yaml.dump(export, open(sys.argv[1], "w"), Dumper=D, sort_keys=False, allow_unicode=True, width=1000)
print("items", len(items))
