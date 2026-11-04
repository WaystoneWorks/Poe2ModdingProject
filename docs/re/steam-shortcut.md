# Playing from Steam (non-Steam game shortcut)

One-time setup, after `cargo xtask deploy-client`:
1. In Steam: **Games → Add a Non-Steam Game to My Library… → Browse…**, select `<repo>/GameFiles/PathOfExileSteam.exe`, **Add Selected Programs**.
2. In the library, right-click the entry → **Properties…**:
   - **Shortcut**: optionally rename it (e.g. "PoE2 Private Server"). Set **Start in** to `"<repo>/GameFiles/"`.
   - **Launch options**:
     ```
     SteamAppId=2694490 SteamGameId=2694490 WINEDLLOVERRIDES="version=n,b" %command%
     ```
     `version=n,b` loads our `version.dll` (the hook) instead of Wine's. The app id makes the Steam API start as Path of Exile 2, which you own.
   - **Compatibility**: tick **Force the use of a specific Steam Play compatibility tool** and pick **Proton Experimental**.

   Steam creates a separate Proton prefix for the shortcut (`steamapps/compatdata/<shortcut id>`); the official install's `compatdata/2694490` is never used.

To play:
1. Start the server from the repo: `cargo xtask server run --release` (Ctrl+C stops it).
2. Launch the shortcut from Steam. The login screen shows "Local Server". With the default `login_mode = "standalone"` sign in with an account name and password (make one offline, [above](../guides/setup.md#accounts-and-characters-offline); Remember Me works). There is no password-less login.

- Admin commands (`!help`, the overlay's Debug tabs) need an account with the admin role: `cargo xtask server run -- account create <name> --password-stdin` then `account role <name> admin` (no account is an admin by default); [server-admin.md](../guides/server-admin.md).
