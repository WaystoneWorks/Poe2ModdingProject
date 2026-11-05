# Architecture

```
client (PathOfExileSteam.exe + version.dll loader + poe_hook_core.dll)
   │  gateway_list.txt → login host:port
   ▼
login-server ──(ticket + instance address)──► client ──► instance-server
   │   ▲                                                  │
   │   └── transfers (pending InstanceDetails) ◄──────────┤
   └──────────── shared services (poe-server process) ────┘
        poe-config · poe-data (game files) · poe-store (DB) · poe-cluster (tickets, login sessions, instances)
```

## Where things are

- Crates, servers, submodules: [crates.md](crates.md). Client DLLs: [client-dll.md](client-dll.md).
- Accounts: [accounts.md](accounts.md). Instances and simulation: [instance-world.md](instance-world.md). Web administration: [web-api.md](web-api.md). Server mods and the client mod check: [mod-host.md](mod-host.md). Stat calculator: [stats.md](stats.md).
- Wire formats: [../protocol/](../protocol/framing.md). RE notes: [../re/README.md](../re/README.md).
- Commands, logs, tests: [../guides/setup.md](../guides/setup.md). Rules: [../../CLAUDE.md](../../CLAUDE.md).

## Design rules
Project rules (no hardcoded opcodes, ports, leagues or game data; subsystems behind traits) are in [../../CLAUDE.md](../../CLAUDE.md). In practice:
- Ports, hosts, paths and command settings live in `modules/server/config/server.toml`; classes, areas and items come from game tables; opcodes and other client-version values live in `modules/protocol/opcodes/<version>/`.
- Traits (cipher, storage, game data source, tickets, login sessions, instance directory) keep implementations swappable (SQLite to Postgres, one process to a split deployment).
- Version-specific RE knowledge (addresses, struct offsets) lives in `docs/re/` and the DLL's pattern signatures, never in server code.
- Mod-friendly: game files are read through an override stack, server commands come from one registry, gameplay events will go through a hook bus ([../guides/modding.md](../guides/modding.md)).
