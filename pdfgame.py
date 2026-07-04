#!/usr/bin/env python3
"""pdfgame — PDF game compiler CLI"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


def cmd_build(args):
    if not args:
        print("usage: pdfgame build <file.game> [-o output.pdf]")
        sys.exit(1)

    source = args[0]
    output = "output.pdf"
    if "-o" in args:
        output = args[args.index("-o") + 1]

    if not os.path.exists(source):
        print(f"error: file not found: {source}")
        sys.exit(1)

    from compiler.compiler import compile_game
    compile_game(source, output)
    print(f"built: {output}")


def cmd_hello(args):
    """Phase 0: generate a hello-world PDF with a JS alert on open."""
    output = args[0] if args else "hello.pdf"
    from pdf_writer.writer import PdfWriter, pdf_dict, pdf_stream

    w = PdfWriter()
    catalog_id = w.alloc_id()   # 1
    pages_id   = w.alloc_id()   # 2
    page_id    = w.alloc_id()   # 3
    js_id      = w.alloc_id()   # 4
    names_id   = w.alloc_id()   # 5

    js_source = 'app.alert("Hello from PDF!\\n\\nThe runtime is alive.");'
    w.add_object(js_id, pdf_stream(js_source, {"Subtype": "/JavaScript"}))

    w.add_object(names_id,
        pdf_dict({
            "/JavaScript": f"<< /Names [(helloScript) {js_id} 0 R] >>"
        })
    )

    open_action = pdf_dict({
        "/S":  "/JavaScript",
        "/JS": f"{js_id} 0 R",
    })

    w.add_object(catalog_id,
        pdf_dict({
            "/Type":       "/Catalog",
            "/Pages":      f"{pages_id} 0 R",
            "/Names":      f"{names_id} 0 R",
            "/OpenAction": open_action,
        })
    )

    w.add_object(pages_id,
        pdf_dict({
            "/Type":  "/Pages",
            "/Kids":  f"[{page_id} 0 R]",
            "/Count": "1",
        })
    )

    w.add_object(page_id,
        pdf_dict({
            "/Type":     "/Page",
            "/Parent":   f"{pages_id} 0 R",
            "/MediaBox": "[0 0 595 200]",
        })
    )

    w.write(output)
    print(f"built: {output}")


def cmd_phase1(args):
    """Phase 1: AcroForm sprite + game loop — a rectangle bouncing across the page."""
    output = args[0] if args else "phase1.pdf"

    import os
    from pdf_writer.writer import PdfWriter, pdf_dict, pdf_stream
    from pdf_writer.acroform import (
        appearance_rect, sprite_widget, label_widget, clickzone_widget
    )

    PAGE_W, PAGE_H = 500, 200
    SPRITE_W, SPRITE_H = 30, 30

    engine_path = os.path.join(os.path.dirname(__file__), "engine", "engine.js")
    with open(engine_path) as f:
        engine_js = f.read()
    engine_js = engine_js.replace("var PAGE_H = 0; /* INJECT:PAGE_H */", f"var PAGE_H = {PAGE_H};")

    game_logic = f"""
var _x = 10;
var _y = 85;
var _vx = 8;
var _ticks = 0;

function update() {{
    _x = _x + _vx;
    if (_x > {PAGE_W - SPRITE_W - 5}) {{ _vx = -8; }}
    if (_x < 5) {{ _vx = 8; }}
    _ticks = _ticks + 1;
    Engine.move("ball", _x, _y);
    Engine.setText("score", _ticks);
}}

Engine.onInput(function () {{
    _vx = _vx * -1;
}});

Engine.start(update, 10);
"""

    bundled_js = engine_js + "\n" + game_logic

    w = PdfWriter()
    catalog_id  = w.alloc_id()   # 1
    pages_id    = w.alloc_id()   # 2
    acroform_id = w.alloc_id()   # 3
    names_id    = w.alloc_id()   # 4
    page_id     = w.alloc_id()   # 5
    js_id       = w.alloc_id()   # 6
    ap_ball_id  = w.alloc_id()   # 7  appearance: ball
    ball_id     = w.alloc_id()   # 8  sprite widget
    score_id    = w.alloc_id()   # 9  label widget
    zone_id     = w.alloc_id()   # 10 click zone

    # JS stream
    w.add_object(js_id, pdf_stream(bundled_js, {"Subtype": "/JavaScript"}))

    # Appearance streams
    w.add_object(ap_ball_id, appearance_rect(SPRITE_W, SPRITE_H, filled=True))

    # Widgets
    w.add_object(ball_id,
        sprite_widget(ball_id, ap_ball_id, "ball",
                      x=10, y=85, w=SPRITE_W, h=SPRITE_H, page_h=PAGE_H))

    w.add_object(score_id,
        label_widget(score_id, "score",
                     x=PAGE_W - 80, y=5, w=75, h=20,
                     value="0", page_h=PAGE_H, font_size=12))

    w.add_object(zone_id,
        clickzone_widget(zone_id,
                         x=0, y=0, w=PAGE_W, h=PAGE_H,
                         page_h=PAGE_H))

    # AcroForm — clickzone last so it sits on top for event capture
    fields = f"[{ball_id} 0 R {score_id} 0 R {zone_id} 0 R]"
    dr = "<< /Font << /Helvetica << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>"
    w.add_object(acroform_id, pdf_dict({
        "/Fields": fields,
        "/DR":     dr,
    }))

    # Names (doc-level JS — entries must be JS actions, not raw stream refs)
    js_action = f"<< /S /JavaScript /JS {js_id} 0 R >>"
    w.add_object(names_id, pdf_dict({
        "/JavaScript": f"<< /Names [(gameScript) {js_action}] >>",
    }))

    # Catalog — OpenAction as belt-and-suspenders (confirmed working in hello.pdf)
    w.add_object(catalog_id, pdf_dict({
        "/Type":       "/Catalog",
        "/Pages":      f"{pages_id} 0 R",
        "/AcroForm":   f"{acroform_id} 0 R",
        "/Names":      f"{names_id} 0 R",
        "/OpenAction": js_action,
    }))

    # Pages
    w.add_object(pages_id, pdf_dict({
        "/Type":  "/Pages",
        "/Kids":  f"[{page_id} 0 R]",
        "/Count": "1",
    }))

    # Page
    annots = f"[{ball_id} 0 R {score_id} 0 R {zone_id} 0 R]"
    w.add_object(page_id, pdf_dict({
        "/Type":     "/Page",
        "/Parent":   f"{pages_id} 0 R",
        "/MediaBox": f"[0 0 {PAGE_W} {PAGE_H}]",
        "/Annots":   annots,
    }))

    w.write(output)
    print(f"built: {output}  ({PAGE_W}x{PAGE_H}pt, 10fps)")
    print("open in Adobe Acrobat Reader — a square should bounce left-right")
    print("click anywhere to reverse direction")


def cmd_debug_static(args):
    """Debug: black rectangle via page content stream — no AcroForms."""
    output = args[0] if args else "debug_static.pdf"
    from pdf_writer.writer import PdfWriter, pdf_dict, pdf_stream
    w = PdfWriter()
    cat_id      = w.alloc_id()
    pages_id    = w.alloc_id()
    page_id     = w.alloc_id()
    content_id  = w.alloc_id()

    content = "0 0 0 rg\n50 80 50 50 re\nf"
    w.add_object(content_id, pdf_stream(content))
    w.add_object(cat_id, pdf_dict({"/Type": "/Catalog", "/Pages": f"{pages_id} 0 R"}))
    w.add_object(pages_id, pdf_dict({"/Type": "/Pages", "/Kids": f"[{page_id} 0 R]", "/Count": "1"}))
    w.add_object(page_id, pdf_dict({
        "/Type": "/Page", "/Parent": f"{pages_id} 0 R",
        "/MediaBox": "[0 0 500 200]", "/Contents": f"{content_id} 0 R",
    }))
    w.write(output)
    print(f"built: {output}  — should show a black square, no AcroForms")


def cmd_debug_widget(args):
    """Debug: minimal AcroForm — one sprite widget, no JS, no clickzone."""
    output = args[0] if args else "debug_widget.pdf"
    from pdf_writer.writer import PdfWriter, pdf_dict, pdf_stream
    from pdf_writer.acroform import appearance_rect, sprite_widget
    PAGE_W, PAGE_H = 500, 200
    w = PdfWriter()
    cat_id      = w.alloc_id()
    pages_id    = w.alloc_id()
    acroform_id = w.alloc_id()
    page_id     = w.alloc_id()
    ap_id       = w.alloc_id()
    widget_id   = w.alloc_id()

    w.add_object(ap_id, appearance_rect(50, 50, filled=True))
    w.add_object(widget_id, sprite_widget(widget_id, ap_id, "test",
                                          x=50, y=75, w=50, h=50, page_h=PAGE_H))
    w.add_object(acroform_id, pdf_dict({
        "/Fields": f"[{widget_id} 0 R]",
        "/DR": "<< /Font << >> >>",
    }))
    w.add_object(cat_id, pdf_dict({
        "/Type": "/Catalog",
        "/Pages": f"{pages_id} 0 R",
        "/AcroForm": f"{acroform_id} 0 R",
    }))
    w.add_object(pages_id, pdf_dict({"/Type": "/Pages", "/Kids": f"[{page_id} 0 R]", "/Count": "1"}))
    w.add_object(page_id, pdf_dict({
        "/Type": "/Page", "/Parent": f"{pages_id} 0 R",
        "/MediaBox": f"[0 0 {PAGE_W} {PAGE_H}]",
        "/Annots": f"[{widget_id} 0 R]",
    }))
    w.write(output)
    print(f"built: {output}  — should show a black square via AcroForm widget")


def cmd_debug_move(args):
    """Debug: open PDF, immediately move ball once — tests Engine.move without timer."""
    output = args[0] if args else "debug_move.pdf"
    import os
    from pdf_writer.writer import PdfWriter, pdf_dict, pdf_stream
    from pdf_writer.acroform import appearance_rect, sprite_widget

    PAGE_W, PAGE_H, SW, SH = 500, 200, 30, 30

    engine_path = os.path.join(os.path.dirname(__file__), "engine", "engine.js")
    with open(engine_path) as f:
        engine_js = f.read()
    engine_js = engine_js.replace("var PAGE_H = 0; /* INJECT:PAGE_H */", f"var PAGE_H = {PAGE_H};")

    game_logic = """
var f = _doc.getField("sprite_ball");
if (!f) {
    app.alert("ERROR: field sprite_ball not found");
} else {
    app.alert("field found! rect=" + f.rect);
    Engine.move("ball", 200, 85);
    app.alert("after move, rect=" + _doc.getField("sprite_ball").rect);
}
"""
    bundled_js = engine_js + "\n" + game_logic

    w = PdfWriter()
    cat_id  = w.alloc_id()
    pages_id = w.alloc_id()
    acro_id = w.alloc_id()
    names_id = w.alloc_id()
    page_id = w.alloc_id()
    js_id   = w.alloc_id()
    ap_id   = w.alloc_id()
    ball_id = w.alloc_id()

    w.add_object(js_id, pdf_stream(bundled_js, {"Subtype": "/JavaScript"}))
    w.add_object(ap_id, appearance_rect(SW, SH, filled=True))
    w.add_object(ball_id, sprite_widget(ball_id, ap_id, "ball",
                                        x=10, y=85, w=SW, h=SH, page_h=PAGE_H))
    w.add_object(acro_id, pdf_dict({
        "/Fields": f"[{ball_id} 0 R]",
        "/DR": "<< /Font << >> >>",
    }))
    js_action = f"<< /S /JavaScript /JS {js_id} 0 R >>"
    w.add_object(names_id, pdf_dict({
        "/JavaScript": f"<< /Names [(gameScript) {js_action}] >>",
    }))
    w.add_object(cat_id, pdf_dict({
        "/Type": "/Catalog",
        "/Pages": f"{pages_id} 0 R",
        "/AcroForm": f"{acro_id} 0 R",
        "/Names": f"{names_id} 0 R",
        "/OpenAction": js_action,
    }))
    w.add_object(pages_id, pdf_dict({
        "/Type": "/Pages", "/Kids": f"[{page_id} 0 R]", "/Count": "1",
    }))
    w.add_object(page_id, pdf_dict({
        "/Type": "/Page", "/Parent": f"{pages_id} 0 R",
        "/MediaBox": f"[0 0 {PAGE_W} {PAGE_H}]",
        "/Annots": f"[{ball_id} 0 R]",
    }))
    w.write(output)
    print(f"built: {output}  — should alert field rect, then move ball to x=200")


COMMANDS = {
    "build":        cmd_build,
    "hello":        cmd_hello,
    "phase1":       cmd_phase1,
    "debug-static": cmd_debug_static,
    "debug-widget": cmd_debug_widget,
    "debug-move":   cmd_debug_move,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("usage: pdfgame <command> [args]")
        print("commands:", ", ".join(COMMANDS))
        sys.exit(1)

    COMMANDS[sys.argv[1]](sys.argv[2:])
