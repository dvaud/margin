### New

- **The concept map's links say more kinds.** Besides *leads to* and *is used instead of*, Margin now proposes links
  that say one concept *needs*, *shapes* or *clashes with* another, found in the text without AI ("X requires Y", "X
  depends on Y", "X influences Y", "X determines Y", "X conflicts with Y", "X is at odds with Y"), each marked *found in
  the text* until you accept it. A concept's card lists them under *What it shapes*, *What shapes it*, *What it needs*,
  *What needs it* and *What it clashes with*, and *Add a link yourself* offers them too. "X undermines Y" is now read
  as *leads to*.
- **The end of a link's line on the map says its kind.** A diamond for *is part of*, a filled arrow for *leads to*, an
  open arrow for *shapes*, a ring for *needs*, a cross for *is used instead of*, a bar across each end for *clashes
  with*, and a plain line for *is related to*. The legend shows each kind on the map with its line. *Is part of* and
  *is used instead of* no longer end in an arrow.
- **Groups have names, and keep them.** Each group of the concept map is named by its two most central concepts until
  you rename it, in the legend, on the map and in the new *Groups* section under the map. A name stays with its group
  between visits and when the groups are found again, as long as the group holds most of the same concepts; a group
  that changed by a third since it was named is marked *changed since it was named*, with *Keep the name*.
- **The AI can draft the groups' names, on request.** *Name the groups* only queues the work: nothing runs until you
  press *Start Claude Code* (or your local model's start) in its panel. The AI reads a few passages of each group, only
  from documents it may read, and gives a short name with a quote that is checked. Its name shows at once, marked *AI
  draft*, until you use it (*Use this name*, *Use all 4 names*) or rename it. Names you gave are never touched.
- **Download the map.** *PNG* (2,400 pixels wide) and *SVG* at the top of the Map tab save the map as a picture for
  slides and papers: title, what was counted, filters, the legend, the map and a foot that says what its marks mean.
  Always light on white; made in the page, nothing is sent anywhere.

### Changes that can alter your results

- **More links are proposed from the text.** Making the glossary again proposes *needs*, *shapes* and *clashes with*
  links where the sentences state them, and proposes *leads to* for "undermines". They count only once you accept
  them.

### Privacy

- **Group names stay on this computer.** They are not shared with a team or sent in a copy for a colleague. The
  passages the AI reads to name a group follow each document's AI setting: a document marked *No AI* is never sent, one
  marked *Only a local AI* only to the local model.

### For developers

- New task kind `group_name` (prompt `group-name-v1`, Haiku then Sonnet, helper `margin-namer`), new module
  `groupnames.py`, tables `concept_group_names` and `concept_group_quotes` (in `sync.common.LOCAL_ONLY`), routes `POST
  …/concept-map/names` and `POST …/concept-map/name-groups` (job `group-names`); link relations `needs`, `needed_by`,
  `shapes`, `shaped_by`, `clashes`.

### Not yet done

- Group names are not shared with a team in this release: each person's names stay on their own computer.
- The links found in the text are English only, as before.
- The downloaded picture is always light; there is no dark version.
