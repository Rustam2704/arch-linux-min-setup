# Passive desktop stall probe

Run: 15.00 min; 8985 process samples at 100 ms; X round trips at 20 ms and i3 GET_VERSION at 100 ms.
Input: XI2 raw counts; counts only. Probe CPU: 13.04% of one core (above 3% target).
Stalls: X >40 ms or i3 >50 ms. Attribution uses ±500 ms input, ±1 s i3 events, and overlapping samples.
Limitations: successful round-trip latencies were not persisted; i3 events outside stall windows were not persisted; the requested CPU overhead limit was not met.
A post-run benchmark of the native all-process `/proc` scan alone took 4.33 ms of CPU per pass (4.33% of one core at 10 Hz).

## Counts

X: 139 stalls; threshold–100 ms: 137, 100–300 ms: 2, >300 ms: 0.
i3: 6 stalls; threshold–100 ms: 6, 100–300 ms: 0, >300 ms: 0.
During activity (categories overlap): typing 0, pointer 51, workspace switch 0, window move 0.
No raw key presses were observed; typing freezes were not reproduced in this run.

## Ten longest stalls

| Time | Probe / ms | Activity | Top 3 CPU (% core) | Swap-ins / major faults | PSI some (cpu/mem/io, ms) | deskd |
|---|---:|---|---|---:|---:|---|
| 2026-10-14T21:19:16.076+03:00 | X 106.0 | pointer | rustdesk(234057) 64.5, zoom(318284) 50.7, pgrep(807653) 50.7 | 0 / 0 | 153.7/13.1/5.4 | S 0.0% |
| 2026-10-14T21:18:38.085+03:00 | X 104.8 | pointer | firefox(2513691) 84.6, Web Content(2828328) 84.6, zoom(318284) 65.8 | 0 / 0 | 186.2/0.0/1.3 | S 0.0% |
| 2026-10-14T21:17:49.264+03:00 | i3 97.1 | pointer | rustdesk(234057) 59.4, python3(806182) 41.6, ffmpeg(805963) 41.6 | 0 / 0 | 56.5/0.0/15.7 | S 0.0% |
| 2026-10-14T21:17:49.303+03:00 | X 96.8 | pointer | rustdesk(234057) 129.4, ffmpeg(805963) 100.7, zoom(318284) 86.3 | 0 / 0 | 204.0/0.0/31.6 | S 0.0% |
| 2026-10-14T21:28:17.612+03:00 | X 90.6 | none counted | kcompactd0(51) 63.7, ffmpeg(816876) 58.4, zoom(318284) 47.8 | 0 / 0 | 111.2/0.0/5.4 | S 0.0% |
| 2026-10-14T21:17:27.124+03:00 | X 88.2 | none counted | Web Content(2828328) 134.5, rustdesk(234057) 57.6, Xorg(953) 50.1 | 2 / 7 | 84.5/0.2/5.3 | S 0.0% |
| 2026-10-14T21:26:05.117+03:00 | X 86.8 | none counted | ffmpeg(814400) 131.3, kcompactd0(51) 79.0, Web Content(2828328) 50.5 | 0 / 0 | 177.0/0.0/3.9 | S 0.0% |
| 2026-10-14T21:19:43.139+03:00 | X 84.2 | pointer | python3(807631) 80.0, Xorg(953) 80.0, firefox(2513691) 60.0 | 0 / 0 | 171.9/0.0/3.2 | S 0.0% |
| 2026-10-14T21:24:18.110+03:00 | X 83.5 | none counted | Web Content(2828328) 149.2, python3(812384) 69.6, Xorg(953) 59.7 | 0 / 0 | 102.7/0.0/3.5 | S 0.0% |
| 2026-10-14T21:19:08.122+03:00 | X 83.3 | none counted | ffmpeg(807310) 89.8, Web Content(2828328) 69.8, Xorg(953) 50.1 | 8 / 10 | 174.0/0.0/7.5 | S 0.0% |

## Busy process ranking

Mean % of one core in stall samples vs other samples (top-eight entries; absent = 0):

| Process | Stall | Outside |
|---|---:|---:|
| Web Content | 67.66 | 70.24 |
| rustdesk | 50.81 | 43.38 |
| zoom | 43.72 | 42.41 |
| Xorg | 42.42 | 20.07 |
| ffmpeg | 34.15 | 22.83 |
| python3 | 32.90 | 41.05 |
| firefox | 11.88 | 10.35 |
| claude | 7.53 | 8.68 |
| kcompactd0 | 3.95 | 2.50 |
| Xephyr | 2.47 | 3.18 |

## Conclusion

X was delayed far more often than i3 (139 vs 6). Xorg averaged 42.4% CPU in overlapping samples vs 20.1% outside; CPU PSI was 62.5 vs 50.2 ms per 100-ms sample. This points to X-server/CPU contention, without isolating one client as the cause.
Xorg reached at least 50% CPU in 86/230 overlapping samples versus 147/8755 other samples; Web Content and Zoom stayed near their non-stall averages, while RustDesk was modestly higher.
deskd was sleeping in 222/230 overlapping samples; swap-ins occurred in 15/145 stalls and major faults in 20/145. Memory pressure is a secondary possibility for those episodes.
The probe itself used 13.04% of a core, so it may have added contention; causal attribution is limited.
