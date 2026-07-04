from .writer import pdf_dict, pdf_stream


def appearance_rect(w, h, filled=True):
    """PDF appearance stream: black filled rect or empty (transparent)."""
    if filled:
        ops = f"0 0 0 rg\n0 0 {w} {h} re\nf"
    else:
        ops = ""
    ops_bytes = ops.encode()
    header = (
        f"<< /Type /XObject /Subtype /Form"
        f" /BBox [0 0 {w} {h}]"
        f" /Resources << >>"
        f" /Length {len(ops_bytes)} >>"
    )
    return header.encode() + b"\nstream\n" + ops_bytes + b"\nendstream"


def appearance_pixels(pixels, scale):
    """
    Build a PDF appearance stream from a B&W pixel grid.
    pixels: list of strings, e.g. ["....XXX.", "....XXXX"]
    scale:  each pixel = scale x scale points
    X = black, . = transparent
    """
    h_px = len(pixels)
    w_px = max(len(row) for row in pixels) if pixels else 0
    w_pt = w_px * scale
    h_pt = h_px * scale

    ops = ["0 0 0 rg"]
    for row_i, row in enumerate(pixels):
        for col_i, ch in enumerate(row):
            if ch == "X":
                px = col_i * scale
                # PDF Y is bottom-up; row 0 is top of sprite
                py = (h_px - row_i - 1) * scale
                ops.append(f"{px} {py} {scale} {scale} re")
    if len(ops) > 1:
        ops.append("f")

    content = "\n".join(ops)
    header = f"<< /Type /XObject /Subtype /Form /BBox [0 0 {w_pt} {h_pt}] /Resources << >> >>"
    return f"{header}\nstream\n{content}\nendstream".encode(), w_pt, h_pt


def sprite_widget(oid, ap_id, name, x, y, w, h, page_h):
    """AcroForm pushbutton widget for a sprite."""
    pdf_y = page_h - y - h
    return pdf_dict({
        "/Type":    "/Annot",
        "/Subtype": "/Widget",
        "/FT":      "/Btn",
        "/Ff":      "65536",
        "/T":       f"(sprite_{name})",
        "/Rect":    f"[{x} {pdf_y} {x+w} {pdf_y+h}]",
        "/MK":      "<< /BG [0 0 0] >>",
        "/AP":      f"<< /N {ap_id} 0 R >>",
        "/F":       "4",
    })


def label_widget(oid, name, x, y, w, h, value, page_h, font_size=14):
    """AcroForm read-only text field for labels."""
    pdf_y = page_h - y - h
    da = f"(0 0 0 rg /Helvetica {font_size} Tf)"
    return pdf_dict({
        "/Type":    "/Annot",
        "/Subtype": "/Widget",
        "/FT":      "/Tx",
        "/Ff":      "1",
        "/T":       f"(text_{name})",
        "/V":       f"({value})",
        "/Rect":    f"[{x} {pdf_y} {x+w} {pdf_y+h}]",
        "/DA":      da,
        "/MK":      "<< >>",
        "/F":       "4",
    })


def clickzone_widget(oid, x, y, w, h, page_h):
    """Invisible button covering the game area — fires Engine.triggerInput() on click."""
    pdf_y = page_h - y - h
    mouse_up = "<< /S /JavaScript /JS (Engine.triggerInput();) >>"
    return pdf_dict({
        "/Type":    "/Annot",
        "/Subtype": "/Widget",
        "/FT":      "/Btn",
        "/Ff":      "65536",
        "/T":       "(clickzone)",
        "/Rect":    f"[{x} {pdf_y} {x+w} {pdf_y+h}]",
        "/H":       "/N",
        "/AA":      f"<< /U {mouse_up} >>",
    })
