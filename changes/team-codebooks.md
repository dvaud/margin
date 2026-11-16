### New

- **A team's codebooks are shared as they are made.** In a team project, the owner's new setting *Codebooks made in this
  project are shared with the team* (Team › People and settings, *Codebooks* card; on by default) shares a codebook kept
  in the project as soon as anyone makes it (fresh, from themes or theory, a copy, a CSV or REFI-QDA file), from their
  own copy; the research log says it was the team's setting. Codebooks made before stay private: their maker sees one
  quiet line on the Codebooks page, *2 of your codebooks in this project are private:* with *Share them*. Anyone can
  still unshare one of their own. Turned off, nothing is taken back and new codebooks are private again. Codebooks kept
  with all projects are not covered.
- **A default codebook for the whole project.** On the same card the owner can choose the *Default codebook for this
  project*: a codebook that ships with Margin, or one of the project's shared codebooks (the owner's own private one is
  shared when chosen). It reaches every copy with the next round or file and takes the place of each computer's own
  setting in this project: the Profile page, a document's Codes panel and the codes new documents get. A page's own
  codebook picker still lets anyone look with another one. Settings › Exploring says *This project uses the team's
  default*; your own setting still holds in your other projects, and wherever the team's codebook has not arrived yet.
  Can change results: new documents get the codes of the team's default codebook, not of your own setting.

### Safer

- Only the owner of the time can set either setting: a copy counts a setting only when its writer owned the project
  when they wrote it, as with roles. A file that carries a setting in the owner's name, which the owner never wrote, is
  refused in the owner's copy and answered there, so the other copies follow the owner again.

### For developers

- `teamcodebooks.py`; the table `team_settings` (one row per setting and writer, merged like `roles` in
  `sync/owner_merge.py`); `GET`/`PUT /api/projects/<p>/owner/codebooks`; `frameworks.chosen` asks for the project's
  default first; `/api/state` has `profile_framework_team`, and `GET …/codebooks` a `team` line. A copy of an older
  Margin leaves the new table aside, so the sync format is unchanged.
