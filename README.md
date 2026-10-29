# dyode_monitoring

Monitoring for [DYODE](https://github.com/nc-intezra/dyode_rust) 2.1.0 and
later: Prometheus alert rules, a Grafana dashboard and a Zabbix 7 template,
all reading the **output box's** local API.

The output box reports both boxes.  The input box's status reaches it
through the diode every `lidi.heartbeat` seconds, so nothing here connects
to the input box or the OT network.  The most important signal is
`dyode_status_age_seconds{side="in"}`: when it grows, the input box, its
NIC, the diode or the output box's receiver has failed.

| Folder | What |
|---|---|
| `prometheus/scrape.yml` | the scrape job (HTTPS, bearer token, the box's certificate) |
| `prometheus/rules/dyode.rules.yml` | 14 alert rules: silent input box, configuration mismatch, aborted transfers, rejected and missing files, module restarts, disk, ARP entry, API refusals |
| `grafana/dyode-overview.json` | dashboard: link health, throughput, modules, free space, API |
| `zabbix/dyode_by_http.yaml` | Zabbix 7.0 template "DYODE by HTTP": one HTTP agent item on `/v1/status`, dependent items, module discovery for both boxes, triggers |
| `examples/` | real `/metrics` and `/v1/status` from a 2.1.0 loopback run |
| `tools/` | generators for the dashboard and template, and `check.py` |

## On the output box

```bash
sudo dyode api-cert --name dyode-out --ip 192.168.50.4     # once
sudo dyode api-token add prometheus --scope read           # one token per client
sudo dyode api-token add zabbix --scope read
```

and in config.yaml (both boxes carry the same file; only the output box
uses `api.out`):

```yaml
api:
  out:
    listen: 192.168.50.4:8443
    tls: {cert: api.crt, key: api.key}
```

The guided setup (`dyode setup`) does the same on its "Local API" screen.
See [docs/API.md](https://github.com/nc-intezra/dyode_rust/blob/main/docs/API.md).

## Prometheus

1. Copy the output box's `/etc/dyode/api.crt` to `/etc/prometheus/dyode-out.crt`
   and the token to `/etc/prometheus/dyode.token`.
2. Add `prometheus/scrape.yml`'s job (keep `job_name: dyode`: the rules use it).
3. Add `prometheus/rules/dyode.rules.yml` to `rule_files` and reload.

## Grafana

Import `grafana/dyode-overview.json` (Dashboards > New > Import) and pick the
Prometheus data source.  Variables: job, output box.

## Zabbix 7

1. Import `zabbix/dyode_by_http.yaml` (Data collection > Templates > Import).
2. Create a host for the output box and link "DYODE by HTTP".
3. Set the macros: `{$DYODE.URL}` = `https://192.168.50.4:8443`,
   `{$DYODE.TOKEN}` = the zabbix token (secret text).
4. The Zabbix server must trust the box's certificate: put `api.crt` in its
   `SSLCALocation`, or turn off "Verify peer" on the "DYODE: Get status" item.

Zabbix 7 can also read `/metrics` with an HTTP agent item and Prometheus
preprocessing, if you prefer to keep one source for both tools.

## Changing things

The dashboard and the template are generated: edit `tools/gen_grafana.py`
or `tools/gen_zabbix.py`, then

```bash
python3 tools/gen_grafana.py grafana/dyode-overview.json
python3 tools/gen_zabbix.py zabbix/dyode_by_http.yaml
python3 tools/check.py        # parses everything; checks every metric and
                              # JSONPath against examples/, and that the
                              # generated files are current
```

CI runs `check.py` and `promtool check rules`.
