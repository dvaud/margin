### New

- **The concept map's group names go to your team.** Names you give the groups (and the AI's drafts and the names
  you used) now travel with the project, in a copy for a colleague, through the shared folder and a team's storage
  space, like the rest of its work. Each copy still finds its groups from its own counts, so a name goes to the group
  there that holds most of its concepts; one that fits no group is kept under *names kept for groups that are not on
  this map*. When two people name the same group, every copy shows the later name, and the group says *Also named “…”
  by …, date*, with *Use this one* in *Rename* and *Remove* beside it. A rename made after seeing a colleague's name
  replaces it; two changes made at the same time on two copies keep the later, and the other stays as a name of its
  own, so nothing a person typed is lost. Between two names for one group a person's comes before an AI draft. A name
  removed on one copy is removed on the others, unless someone changed it afterwards. A group named by a colleague says
  *named by* and their name; *Keep the name* keeps it theirs. A wrong clock cannot win for ever: a change made after
  seeing another is always dated after it, and a name dated more than ten minutes ahead waits.
- **Zoom on the concept map.** *Zoom in*, *Zoom out* and *Whole map* over the map; Ctrl or ⌘ and the wheel, a
  trackpad's pinch, and the keys **+**, **−** and **0**. Zoomed in, drag the map (or use the arrow keys) to move
  around it. Words grow more slowly than the map, and from twice the size on every concept's name shows. A downloaded
  picture is still the whole map.

### Changes that can alter your results

- **The AI's link tasks propose *needs*, *shapes* and *clashes with*** (prompt `link-v2`), the kinds the text
  patterns and you could already give, each with a quote from both terms' passages, marked as the AI's and yours to
  accept, change or reject. Pairs judged again may get one of these kinds where they had *related* before; links
  judged earlier are not asked again.
- **Two names for one map group: the later is shown.** Before, the name that fitted the group best was shown; now a
  person's name comes before an AI draft, then the later one, so every copy of a shared project shows the same name.

### For developers

- `concept_group_names` and `concept_group_quotes` left `sync.common.LOCAL_ONLY` for `OWN_RULES`, merged by
  `groupnames.merge` (new columns `person_id`, `changed_by`, `history_json`; removals as `sync_removed` rows of kind
  `group_name`; incoming rows checked by `groupnames.valid_row`; local changes dated by `groupnames.clock`).
- `evaluation` compares two runs' link answers pair by pair, a pair turned round read from its smaller term. The AI's
  `group_name` tasks stay local (`sharing.LOCAL_TASK_KINDS`).

### Not yet done

- Group names' sync is tested with the same merge a project file goes through, not end to end through a real shared
  folder or storage space. A colleague's file may carry a third person's names (as it may carry their reviews), but it
  never changes a name you changed last.
- A downloaded picture of the map is always light, and the links found in the text are English only.
