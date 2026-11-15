### Fixed

- **A codebook kept in one project no longer breaks the others.** The codebook chosen for document profiles is one
  setting for the whole app, but a codebook kept with a project is only in that project. Choose one there, open
  another project, and Themes, Codes and a document's codes said the codebook was not available until you picked
  another one by hand. Now each project uses the chosen codebook when it has it and the SDG targets when it does not;
  the first project keeps your choice, and Settings shows the codebook the open project uses. Documents added to the
  other project get the SDG targets' keyword codes again (that step had failed quietly). No other result changes.
