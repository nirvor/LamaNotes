# LamaNotes performance contract

LamaNotes optimizes perceived work, not an artificial single score. A local
file must appear without waiting for the RackNerd Library. Common reading and
editing paths stay lightweight; uncommon renderers and tools may load later.

## Budgets

On a representative supported Windows 11 machine:

- a warm local draft should reach its editor in less than 1 second;
- a cold WebView2 profile should reach it in less than 2 seconds;
- switching an already rendered local file into its warmed editor should take
  less than 100 ms;
- the local loopback proxy should add no material delay to RackNerd requests;
  and
- server-side health and index generation should remain small compared with
  the public network roundtrip.

These are regression budgets, not promises for every PC or connection. Record
the exact executable, commit, profile mode and machine when comparing runs.

## Reproducible Windows measurement

Build the exact commit, then run the isolated-profile harness:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\windows-client\benchmark-startup.ps1 `
  -ExePath .\windows-client\dist\LamaNotes\LamaNotes.exe `
  -Profile Warm `
  -Runs 5 `
  -OutputPath .\output\performance\windows-warm.json
```

Repeat with `-Profile Cold`. The harness creates a temporary `LOCALAPPDATA`
root, opens a local draft, reads the native telemetry emitted by the bundled
client and removes the isolated profile after closing the measured process. It
does not use or modify the normal LamaNotes profile.

## Reference before the July 2026 startup pass

The installed `09a6bb7661aedd64258cb5048991c1e427bb8da5` client was measured
on one Windows 11 workstation before this optimization:

| Path                                                 |       Result |
| ---------------------------------------------------- | -----------: |
| Warm local-draft editor, median of four settled runs |       738 ms |
| Cold-profile local-draft editor                      |     1,525 ms |
| Warm browser part                                    |       150 ms |
| Warm editor route part                               |        41 ms |
| Rendered Markdown to editor after chunk warm-up      |        57 ms |
| Main-process working set                             | about 110 MB |

The same session measured the loopback static shell at below 1 ms median,
RackNerd API calls from the workstation at roughly 140-165 ms median and the
container health endpoint at roughly 2 ms median. The useful optimization
boundary is therefore fewer first-load roundtrips, less startup parsing and
less bundled UI code. A larger server or a more complex sync layer would not
address the measured bottleneck.

## July 2026 startup pass

The unsigned release candidate was measured on the same workstation. Windows
code-signing and installation still belong to the release gate, so small
native-start differences are not treated as a product claim.

| Change                                           | Before | Candidate |
| ------------------------------------------------ | -----: | --------: |
| Initial application JavaScript                   | 311 kB |    204 kB |
| Initial application JavaScript, gzip             | 108 kB |     79 kB |
| Home illustration                                | 522 kB |     14 kB |
| Main-process working set for a local draft       | 110 MB |    105 MB |
| File handoff into an already open window, median | 310 ms |    282 ms |
| Settled native local-draft start                 | 0.78 s |    0.82 s |

The last row remains in the same sub-second band and is not counted as a
speed-up. The useful gains are less code and memory on every start, a faster
existing-window file handoff and one authenticated RackNerd bootstrap request
instead of separate config and index roundtrips. Local files also no longer
initialize the upstream HTTP pool; Library starts warm that pool in parallel
with the WebView import.

## Implementation rules

- Keep local file opening independent of auth and network.
- Combine only safe, body-free startup metadata. Never preload note bodies.
- Prefer one shared cache with a bounded lifetime over a second source of
  truth.
- Defer rich editors and visual renderers until the active content needs them.
- Do not trade keyboard support, accessible names, conflict checks or update
  verification for a faster number.
- Compare the exact release build before publishing and keep the raw JSON
  output outside Git.
