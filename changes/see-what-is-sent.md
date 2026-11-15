### New

- **See what is sent.** Wherever work waits for Claude Code, the line "Claude Code sends the passages inside the tasks
  it takes to Anthropic" now has a *See what is sent* button. It opens the next batch word for word as Claude Code's
  helper receives it: the instruction once, then each task's text with its document and pages, and the connector's
  whole reply to copy. *Show the batch after* goes on through the queue. Looking takes no task and records nothing as
  sent; a document marked *Only a local AI* or *No AI* never appears in it, as it never leaves.

### Tests

- `test_queue.py`: the preview is the batch `next_tasks` then hands over (same instruction, same texts, same order),
  claims nothing, writes no ledger row, leaves out a document marked No AI, and pages on; the route answers 400 for an
  unknown kind.

### Not yet done

- Claude Code's own part of what it sends (the helper's instructions from the Margin plugin, the same for every
  project, and its own working) is named in the dialog but not shown.
