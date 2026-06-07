# Supabase Realtime setup (for the live dashboard)

The judge-facing dashboard (Features.md §9) subscribes to Postgres changes via
**Supabase Realtime**. Every state-changing API endpoint writes through
`RelationalMemory`, so each change lands in Postgres — but Realtime only
broadcasts changes for tables you explicitly enable.

## Enable replication

In the Supabase dashboard: **Database → Replication →
`supabase_realtime` publication → manage tables**, and enable Realtime for at
least:

| Table          | Why the dashboard needs it                                   |
|----------------|--------------------------------------------------------------|
| `world_states` | The stacked-stones visual — every engine update appends a snapshot row here. **Primary signal.** |
| `checkins`     | The live check-in feed (including the logged voice-escalation outcomes). |

Optional, for a richer console:

| Table              | Adds                                                  |
|--------------------|-------------------------------------------------------|
| `reflection_notes` | Shows new insights appearing as the Reflection Agent runs. |
| `goals`            | Reflects goal creation / re-planning.                 |

## Notes

- A new `world_states` row is written on **every** world change (the engine
  appends rather than overwrites), so the dashboard can animate the stack growing
  and even scrub history. Subscribe to `INSERT` on `world_states`.
- `checkins` is append-only; subscribe to `INSERT`.
- No schema changes are required — `memory/schema.sql` already creates these
  tables. This is purely a dashboard toggle.
- Realtime respects Row Level Security. For the hackathon demo the dashboard uses
  the service role (or RLS is left permissive); tighten before any real launch.
