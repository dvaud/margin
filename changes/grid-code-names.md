### Improved

- **A grid of codes with names shows many of them at once.** On Themes (*Themes by code*) and on Codes (*Documents by
  code*), a codebook whose codes are names ("Public trust in medical AI") had each name on one line in typewriter
  letters, so every column was as wide as its name and four of thirty-two codes showed at a time. Now the names are
  in the interface's own letters: wrapped, a column each, while the grid fits the page; and once it would not, set at
  a slant over narrow columns, on two lines at most, so that about thirteen codes show on the page and twenty-two in
  *Full screen* (on a 1,400-pixel window). The column under the pointer has its name darkened, and hovering a name
  still says the whole code with its description. Codebooks whose codes are short marks ("3.4") look as they did.
  Changes no result.

### Tests

- The heat grid's column heads: one helper on both pages, names never on one unbroken line, and the header row held
  as a whole in *Full screen* (`tests/test_update_and_grid.py`).
