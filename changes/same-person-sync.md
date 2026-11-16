### New

- **Your private work on both of your computers.** If you use two computers, each is an account of its own in the
  team, and the owner can mark both as you. With a storage space, *Team* › *People and settings* now has a card
  *Your other account*: press *Send my private work…* on one computer and then on the other, and your private checks,
  sets of themes, codebooks, notes, research log entries and links between terms go between the two from the next
  rounds, while staying private. Either computer can then share or take back what the other made (the computer that
  made it carries it out at its next round, so colleagues see it shared by its maker). Each computer can
  stop it at any time (*Stop…*); what already arrived stays. On a plain shared folder it is not offered. Does not
  change results.

### Privacy

- **Your private work reaches only your other account, and only with its own consent.** The owner's mark that two
  accounts are one person sends nothing: each account must turn it on itself, on its own computer, and both must be
  in the team. Before turning it on, both computers show a check code made of the two accounts' keys: the same code on
  both means the account is really your other one. The work is locked with a key made for each file, which only your
  other account's own key opens: colleagues cannot read it, and the storage company sees only that a file was written
  and its size. What arrives stays private there and is never sent to colleagues, in the shared folder, the storage
  space or a zip. It stops by itself when either account leaves or is removed, or the owner no longer marks both as
  you. A private item of someone else's in your copy is shared only by a mark in its owner's own file, so no member can
  publish it by writing a mark in theirs. If the team's list of members gives your account other keys than your
  computer's own, nothing goes, and the card says so.

### For developers

- `sync/selfsync.py` (its docstring has the threat model): statements in `parts/<part>/m/pair.json`, private bundles in
  `parts/<part>/p/<stream>.<number>` sealed to the other account's X25519 key; `PUT`/`DELETE
  /api/projects/<p>/space/self-sync`, and `"self_sync"` in `GET …/shared-folder`. `sharing.state`, `sharing._may`,
  `sharing.receive`, `merge._may_replace` and the note and research log rules treat the two accounts as one maker
  while the pair holds. Older copies leave the new files aside (`formats.py`).

### Not yet done

- A codebook or a link between terms removed on one computer is not removed on the other.
