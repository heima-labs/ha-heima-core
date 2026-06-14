# Heima Developer Debug Dashboard

`scripts/generate_debug_dashboard.py` generates a Lovelace dashboard from a live Home Assistant
instance. It is intended for development and operations monitoring, not for resident-facing use.

The generator reads:

- the Heima config entry diagnostics;
- live Home Assistant states;
- configured rooms and reactions;
- runtime diagnostics, learning module status, lighting runtime state, and active reactions.

It emits a standard Lovelace YAML view using built-in cards only.

## Usage

```bash
source scripts/.env
.venv/bin/python scripts/generate_debug_dashboard.py \
  --ha-url "$HA_URL" \
  --ha-token "$HA_TOKEN" \
  --mode generic \
  --out /tmp/heima_dev_debug_dashboard.yaml \
  --dump-inventory /tmp/heima_dev_debug_inventory.json
```

Use `--mode test-lab` to include test-lab fixture entities and the reset action when present.

The generated YAML can be pasted into a Home Assistant dashboard raw editor, or copied into a
dashboard YAML file managed by the test instance.

## Output Shape

The dashboard contains:

- runtime overview and fast history;
- occupancy/people, heating, and security entity groups;
- active runtime reactions;
- configured reaction table;
- lighting runtime summary;
- one section per configured room, with discovered room entities and history;
- optional developer/test-lab action buttons;
- uncategorized Heima entities for inspection.

The inventory JSON is useful when the dashboard misses an entity or when discovery needs tuning.
