# FuxNoten Elternportal Calendar for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration that syncs upcoming
graded assignments and tests ("Leistungskontrollen" / "Klassenarbeiten") from the
[FuxNoten](https://www.fuxmedia.de/) Elternportal into a Home Assistant calendar.

FuxNoten's Elternportal does not offer an iCal export or subscription feed. This integration
logs into the portal's parent-facing web UI (using its internal, undocumented JSON API), reads
the calendar entries, and creates matching events in a calendar of your choice - so you can see
upcoming tests in your existing family calendar, dashboards, or automations.

## Features

- Logs in with your Elternportal credentials, reads the calendar, logs out again - no
  persistent session is kept between syncs.
- Only graded assignments / tests are synced (holidays and public holidays are intentionally
  skipped).
- Runs once per day at a time you configure.
- Keeps track of which events were already created, so re-runs never create duplicates.
- Exposes a sensor with the timestamp of the last sync and how many events were fetched/created.

## Disclaimer

This integration relies on FuxNoten's internal web API, which is neither documented nor
officially supported for third-party access. It may break without notice if FuxNoten changes
their portal. Use at your own risk.

## Installation

### Via HACS (recommended)

1. In HACS, add this repository as a custom repository (category: Integration):
   `https://github.com/fion-private/ha-fuxnoten-calendar`
2. Install "FuxNoten Elternportal" from HACS.
3. Restart Home Assistant.

### Manual installation

1. Copy the `custom_components/fuxnoten` directory into your Home Assistant `config/custom_components`
   directory.
2. Restart Home Assistant.

## Configuration

Configuration is done entirely through the Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**, search for "FuxNoten Elternportal".
2. Enter:
   - **School number**: the number in your portal's URL, e.g. `123456` for
     `https://123456.fuxnoten.com`.
   - **Username** and **Password**: your Elternportal login credentials.
3. After the credentials are verified, choose:
   - **Child**: which of the children linked to your account to sync.
   - **Target calendar**: an existing Home Assistant calendar entity (e.g. a
     [Local Calendar](https://www.home-assistant.io/integrations/local_calendar/) or any calendar
     integration that supports the `calendar.create_event` service) to create events in.
   - **Daily sync time**: the time of day the portal is checked for new events.

If you have multiple children with separate Elternportal logins, add the integration again for
each child.

## How it works

On each sync, the integration:

1. Requests the `fux-channel=beta` cookie (required to reach the current portal UI rather than
   the legacy admin interface).
2. Logs in via the portal's AJAX login endpoint.
3. Reads the calendar's JSON feed for a rolling window (7 days in the past to 120 days in the
   future).
4. Filters events to `category_id == 2` ("Leistungen").
5. Logs out again.
6. Compares the fetched events against a local store of previously-created event IDs, and calls
   `calendar.create_event` on your chosen calendar only for the ones that are new.

## Development

```bash
pip install -r requirements-dev.txt
ruff check custom_components tests
ruff format custom_components tests
mypy custom_components
pytest
```

CI runs [hassfest](https://developers.home-assistant.io/docs/creating_integration_manifest/#hassfest)
and [HACS](https://hacs.xyz/) validation, linting (ruff + mypy), and the unit test suite on every
push and pull request.

Only the pure, Home-Assistant-independent parts of the integration (URL building, HTML/JSON
parsing) are covered by unit tests. The parts that talk to Home Assistant itself
(`config_flow.py`, `coordinator.py`, `__init__.py`, `sensor.py`) are best verified against a real
Home Assistant instance, since the portal's undocumented API and Home Assistant's own APIs can
both change.

## License

MIT, see [LICENSE](LICENSE).
