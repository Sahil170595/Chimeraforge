# TR116 Scripts

Helper notes for running TR116 without starting benches automatically.

## Power Sampling (manual)
1) Start sampling in a separate shell before the run:
```
nvidia-smi --query-gpu=power.draw,utilization.gpu,temperature.gpu --format=csv,noheader,nounits -l 1 > power_log.csv
```
2) After the run, stop the sampler (Ctrl+C) and trim the log to the active inference window using your run timestamps.
3) Compute mean power over the active window, then derive joules/token: `(mean_watts * active_seconds) / tokens_generated`.

## Run Wrappers (optional)
Add per-model batch scripts here if you want to fire the single- and multi-agent matrices in one command. Keep outputs under `experiments/TR116/results/**` per the PRD.
