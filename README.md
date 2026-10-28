# dyode_monitoring

Monitoring for [DYODE](https://github.com/nc-intezra/dyode_rust) (Rust + lidi):
dashboards, alert rules and templates for the API the output box serves
from DYODE 2.1.0 on.

Planned contents:

| Folder | What |
|---|---|
| `prometheus/` | scrape configs and alert rules (`dyode_status_age_seconds`, rejected and missing files, module restarts) |
| `grafana/` | dashboards for both boxes and the relayed OT metrics |
| `zabbix/` | Zabbix 7.x templates: HTTP agent items on `/v1/status` and `/metrics` |

Everything here reads the output box (IT side). Nothing here connects to
the input box or the OT network: DYODE carries the input box's status, and
relayed OT metrics, through the diode.
