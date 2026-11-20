"""QR code helper. Uses the small pure-Python `segno` package (see requirements.txt)."""


def qr_data_uri(text):
    """Return a data: URI (SVG) of a QR code for `text`, or None if segno isn't installed."""
    try:
        import segno
    except ImportError:
        return None
    return segno.make(text, error="m").svg_data_uri(scale=6, border=2)
