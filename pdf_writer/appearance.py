def pixel_art_stream(rows, scale):
    """
    rows:  list of strings, e.g. ["....XXX.", "....XXXX"]
    scale: each pixel = scale x scale points
    X = black filled, . = transparent
    Returns (bytes, width_pt, height_pt)
    """
    h_px = len(rows)
    w_px = max((len(r) for r in rows), default=0)
    w_pt = w_px * scale
    h_pt = h_px * scale

    ops = ["0 0 0 rg"]
    for row_i, row in enumerate(rows):
        for col_i, ch in enumerate(row):
            if ch == "X":
                px = col_i * scale
                py = (h_px - row_i - 1) * scale  # PDF Y is bottom-up
                ops.append(f"{px} {py} {scale} {scale} re")
    if len(ops) > 1:
        ops.append("f")

    content = "\n".join(ops).encode()
    header = (
        f"<< /Type /XObject /Subtype /Form"
        f" /BBox [0 0 {w_pt} {h_pt}]"
        f" /Resources << >>"
        f" /Length {len(content)} >>"
    )
    return header.encode() + b"\nstream\n" + content + b"\nendstream", w_pt, h_pt


def solid_rect_stream(w_pt, h_pt):
    """Solid black filled rectangle appearance stream."""
    content = f"0 0 0 rg\n0 0 {w_pt} {h_pt} re\nf".encode()
    header = (
        f"<< /Type /XObject /Subtype /Form"
        f" /BBox [0 0 {w_pt} {h_pt}]"
        f" /Resources << >>"
        f" /Length {len(content)} >>"
    )
    return header.encode() + b"\nstream\n" + content + b"\nendstream"


def empty_stream():
    """Empty (transparent) appearance stream."""
    header = b"<< /Type /XObject /Subtype /Form /BBox [0 0 1 1] /Resources << >> /Length 0 >>"
    return header + b"\nstream\n\nendstream"
