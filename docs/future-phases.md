# Future Phases (Not Implemented Yet)

## Memory

- Replace file-based memory facade with structured store (SQLite/Postgres/vector DB)
- Add user/session memory policies (TTL, summarization, retention)

## Intent & Tools

- Expand intent taxonomy for high-confidence routing
- Add explicit tool contracts (calendar, reminders, home actions, app triggers)

## Phone Integration

- Notification delivery and action confirmations
- Call/message trigger adapters

## Notifications

- Scheduler + delivery queue
- Priority/quiet-hour policy

## Wake-word and sensor/event ingress

- Dedicated wake-word edge flow
- `/event` expansion for PIR/mmWave/BLE presence

## Camera/identity recognition

- Event-based capture pipeline
- Identity confidence scoring + privacy controls
