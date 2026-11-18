### Fixed

- **The local model no longer starts on a button that is not its own.** *Name the themes*, when every theme came from
  documents marked *Only a local AI*, started the local model at once; so did any other work only the local model may
  do (labels, links, group names of such documents) when another button asked for it. That work now waits for the
  local model's own *Start*, as it already did beside Claude's work, and nothing is loaded before. Work started by the
  local model's own button (*Read them now on this computer*, or *Start* in the Profile page's local panel) still needs
  no second click.
- **The Themes page says which AI names the themes.** It said "Claude, on your plan, reads the passages of each
  theme" even when their documents may only be read on this computer. It now names the local model when it is the one
  that reads them, and counts the themes each AI names, and those no AI may read, when they differ. The lines of the
  codebook from theory, a code's AI definition and the concept map's group names say the local model starts with its
  own *Start* too.

### Tests

- `tests/test_local_gate.py`: an all-local gate waits for its Start; labels of local documents and theme naming wait
  until it is pressed; `themes.readers` counts who names the themes. `tests/test_views_codebooks_and_themes.py`: the
  Themes page's AI line for each case. The Profile page's local panel starts its job as the local model's own Start.

### Not yet done

- The sidebar offers the local model's *Start* only while no other job runs; otherwise it is on the job's own page.
- Work that asks the local model one request at a time (comparing the routes, following references) says "1 task
  waits" before its *Start*, whatever the number.
