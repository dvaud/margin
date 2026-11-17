### New

- **Set the role of many documents at once.** In *Documents*, tick the documents and choose *Role* in the bar at the
  foot of the window: evidence, theory or your working documents. Margin asks once, marks them all and offers *Undo*,
  which gives each document the role it had. The research log keeps one entry for the batch, naming the documents.
  A *Non-scientific* mark stays as it is; in a shared project a Member's marks are proposals, as one document's are.
  Theory and working documents are left out of what counts, as before: can change results made from now on.

### For developers

- `docrole.set_roles` and `PUT /api/projects/<p>/document-roles` (`{doc_ids, role, why?}`): one role for many
  documents, by the rules of one, with one research-log entry (`subject_kind` "documents", `data.was` per document).
