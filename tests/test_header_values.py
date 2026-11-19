"""A header value never carries a line break: a file name from someone's zip cannot add headers of its own."""
from margin.gui.api_common import _disposition
from margin.gui.server import Handler

EVIL = "a\r\nContent-Type: text/html\r\nX: b.pdf"


def test_the_disposition_of_a_name_with_line_breaks_is_one_line():
    d = _disposition(EVIL)
    assert "\r" not in d and "\n" not in d and d.startswith('attachment; filename="a Content-Type')


def test_the_handler_sends_no_line_break_in_a_value():
    h = Handler.__new__(Handler)  # no socket: only the header buffer is used
    h.request_version, h._headers_buffer = "HTTP/1.1", []
    h.send_header("Content-Disposition", EVIL)
    h.send_header("Content-Length", 12)
    assert h._headers_buffer == [b"Content-Disposition: a  Content-Type: text/html  X: b.pdf\r\n", b"Content-Length: 12\r\n"]
