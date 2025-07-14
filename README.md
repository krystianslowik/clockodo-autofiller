# clockodo autofiller

fills your clockodo timesheet so you don't have to

## what it does

• bulk creates time entries for date ranges
• randomizes start times (13:30-14:00 by default)
• auto-schedules 30min breaks
• skips weekends and holidays
• doesn't break when you mess up the config

## setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

edit `.env` with your clockodo credentials:
```
CLOCKODO_API_USER=your.email@example.com
CLOCKODO_API_KEY=your_api_key_here
```

## usage

```bash
# test run (safe)
python clockodo_scheduler.py --dry-run

# actual run (creates entries)
python clockodo_scheduler.py

# custom dates
python clockodo_scheduler.py --start-date 2025-05-01 --end-date 2025-05-31
```

## config.json

```json
{
  "customer_id": 2005009,
  "service_id": 739320,
  "start_date": "2025-05-01",
  "end_date": "2025-05-31",
  "excluded_dates": ["2025-05-29", "2025-06-09"],
  "timezone": "Europe/Berlin",
  "start_time_options": ["13:30", "14:00"],
  "end_time": "23:30"
}
```

| Option | Description | Default |
|--------|-------------|---------|
| `customer_id` | Clockodo customer ID | Required |
| `service_id` | Clockodo service ID | Required |
| `billable` | Whether entries are billable | `true` |
| `start_date` | Start date (YYYY-MM-DD) | Required |
| `end_date` | End date (YYYY-MM-DD) | Required |
| `excluded_dates` | Array of dates to skip | `[]` |
| `timezone` | Timezone for time calculations | `"UTC"` |
| `start_time_options` | Possible start times | `["11:00", "11:30", "12:00"]` |
| `end_time` | Fixed end time | `"21:00"` |
| `external_app` | External app identifier | `"Python Scheduler"` |


## how it works

1. reads date range from config
2. filters out weekends and excluded dates
3. randomizes start times
4. calculates break placement (30min at midpoint)
5. creates 2 entries per day (before/after break)
6. sends to clockodo api with rate limiting

that's it.