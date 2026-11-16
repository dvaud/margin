### New

- **The local model starts only when you press its own Start.** In work that Claude also does (a check, labelling
  passages, naming themes, judging pairs of terms, reading theory documents), the documents marked *Only a local AI*
  and the AI mix's share used to be read by your local model as soon as the work began. Now starting Claude and
  starting the local model are two separate clicks: the local part waits beside Claude's, says how much waits and
  whether this computer has the memory for the model, and nothing loads the model until you press its Start. One
  Start covers the whole job; the local model then reads beside Claude, and its own Stop lets it finish the item in
  hand and wait again. Work only the local model does, started by its own button, still needs one click.
- **At your plan's usage limit, "Carry on with the local model" offers its Start** instead of starting the local model
  by itself.

### Fixed

- **A check stopped while only its local excerpts were left is kept**: Claude Code's part is no longer thrown away;
  the excerpts wait for *Read them now* on the result.
- **Too little memory no longer ends the local part.** It waits, with the numbers, for *Start it anyway*, in the same
  job.

### For developers

- Each job has a local gate (`localgate.py`): `job.local` in the job's view (`gate` wait/go/force, `waiting`, `noun`,
  `model`, `memory`, `problem`), `POST /api/jobs/<id>/local/start` (`{"force"}`) and `/local/stop`, and
  `progress.model = {"who": "local", "phase": "ready"}` while it waits. `GET …/queue`'s `at_limit` gains
  `offer_local`; `POST …/queue/run` takes `{"local": "limit"}`. The command line and the connector have no gate.

### Tests

- `tests/test_local_gate.py`: the gate waits for its Start, Start it anyway, the local Stop after the item in hand, a
  memory refusal that waits again, labels and a check by queue in real jobs, an all-local job in one click, the
  endpoints, and the offer at the plan's limit.
