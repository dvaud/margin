### Changed

- **Only the AI that works in a job shows.** The sidebar's work box and the AI run panel showed both the house (this
  computer) and the cloud (Claude) for every AI job, the one with no work in it as a dashed empty tile; it read as if
  both were at work. Now only the engine at work shows, and its half of the bar takes the whole width; a job for both
  still shows both, this computer on the left and Claude on the right.

### Fixed

- **A click on the sidebar's work box opens the work again.** *Reading excerpts with the local model* had no place of
  its own, so its box linked to the Overview: from the Overview, the click did nothing. It now opens the result it
  reads for. The same was true of a stronger model's second reading (now its result), *Answering the queue here*
  (Settings › AI), the comparison of the local model with Claude (Settings › AI), *Trying the codebook* (Codebooks),
  *Checking for retractions* (Bibliography) and the new reader's check of documents (Documents). A test now asks
  every kind of job the app starts for a place of its own.
