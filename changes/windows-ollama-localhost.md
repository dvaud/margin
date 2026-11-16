### Fixed

- **On Windows, Margin sees Ollama when it runs.** After *Install Ollama* the card stayed on "Starting Ollama…", and
  after a reload on "Ollama is starting…" until its minute ran out, although Ollama was running. Windows looks
  "localhost" up as IPv6 first, Ollama listens on IPv4 only, and Windows takes about two seconds to say nothing
  listens there: longer than Margin's quick look for a running model server. Margin now asks 127.0.0.1 first for
  any model server on this computer, which also takes about two seconds off every request to a local model on
  Windows. When Ollama answers already, the card no longer leaves the install's "Starting Ollama…" bar in place.

### Tests

- `tests/test_localhost_ipv4_first.py`: localhost goes to 127.0.0.1 first with the request kept whole, a server on
  IPv6 alone is still reached, a timeout is not tried twice, other addresses are untouched, and the quick look finds
  a stand-in Ollama listening on 127.0.0.1 only.

### Not yet done

- Not yet tried with a real Ollama on Windows.
