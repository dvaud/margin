### Fixed

- **Your local model can name themes again.** A local model (Ollama, LM Studio) could never give a theme a name:
  Margin told it the form of its answer but left out the description, so the model could not write one and every
  answer was turned down three times. Its quotes were fine; the message after naming wrongly said they "did not check
  out". Themes from documents marked Only a local AI are now named and described by your local model. Can change
  results: those themes get the AI's name and description in place of their key terms.
- **Let the AI name the themes asks the AI again.** After the AI could not name a theme, pressing the button again
  ended at once and named nothing. Each press now asks the model again, with what was wrong last time.
- **A theme the AI could not name says so on the Themes page.** Above the themes, a notice says how many themes the AI
  could not name and why, in plain words, with *Try again*; each such theme's card says it too, with the technical
  details folded away, and so does the theme's own page. The message after naming no longer has to be caught before it
  goes. Does not change results.

### Tests

- The JSON schema sent to a local model keeps every field of each kind of answer; a stand-in local model that writes
  only what the schema allows names themes; a failed naming is shown and asked again.
