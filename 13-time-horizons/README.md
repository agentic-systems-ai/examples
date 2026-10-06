# 13 · How long can an agent work?

Companion code for the post [How long can an agent work? Time horizons explained](https://www.agenticsystems.ai/blog/time-horizons/).

`fit_horizon.py` estimates an agent's **time horizon** with the method METR uses: for each task you know how long a skilled human takes and whether the agent succeeded. Fit a logistic curve of success against log task length, and read off the task length where the agent succeeds 50% (or 80%) of the time. Bootstrap resampling gives the uncertainty.

It needs no API key and no third-party packages.

## Run it

```bash
python fit_horizon.py                    # synthetic agent with a KNOWN 60-minute horizon: can we recover it?
python fit_horizon.py --tasks 30         # ...with only 30 tasks?
python fit_horizon.py --tasks 1000       # ...with 1,000?
python fit_horizon.py --csv my_tasks.csv # your own results
```

Output from these runs (synthetic data, fixed seed):

```
SYNTHETIC agent - true 50% horizon 60 min, true 80% horizon 21 min

150 tasks, 89 successes
50% time horizon:   54 min   (90% interval 38 min – 74 min)
80% time horizon:   19 min   (90% interval 13 min – 30 min)
```

With 30 tasks the 90% interval for the 50% horizon is 27 minutes to 2.3 hours. With 1,000 it's 58 to 73 minutes. **The number of tasks decides whether a horizon estimate means anything.**

## Your own data

`my_tasks.csv` is an **example file with made-up rows**. Replace it with your own eval results: one row per task, with how long a skilled person takes (`human_minutes`) and whether your agent succeeded (`success`, 0 or 1).

```
human_minutes,success
2,1
45,1
120,0
```

To estimate human times honestly, time a few people on a sample of tasks; guesses are usually too optimistic. You'll also need tasks spread across a wide range of lengths, or there's no slope to fit.
