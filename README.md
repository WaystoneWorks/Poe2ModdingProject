# Poe2ModdingProject

A private server for **Path of Exile 2 (client 0.5.5f)**, written in Rust and built for client and server modding. It is a personal, educational project in early development: login, accounts, multiplayer towns, server-generated areas, a launcher and a web admin work; combat, monsters and items do not exist yet.

This repository is the hub: docs, reverse-engineering notes and dev tooling. The code lives in submodules under `modules/`.

- **Players:** use the [launcher](docs/guides/client.md).
- **Hosts:** see the [hosting guide](modules/server/docs/hosting.md).
- **Developers:** `git clone --recursive`, then follow the [setup guide](docs/guides/setup.md).

More: [what is left to do](docs/PLAN.md), [repository overview](docs/overview.md), [all documentation](docs/index.md).

## Disclaimer

This is an unofficial, fan-made project for personal and educational use. It is **not affiliated with, endorsed by or connected to Grinding Gear Games**; "Path of Exile" is their trademark. **No game files are distributed** here (no assets, bundles, tables or executables): you need your own legal copy of the game, and the project only reads it from your machine. The client hook is meant for the private server; on official servers it can be used in an **observe-only** (read-only) mode, described in the [official mode guide](docs/guides/official-mode.md). Even then it patches game code in memory to observe, which the game's anti-cheat may detect, so do not use it on an account you care about. You use all of this at your own risk. More: [SECURITY.md](SECURITY.md), [CONTRIBUTING.md](CONTRIBUTING.md); licensed under MIT ([LICENSE](LICENSE)).
