"""compile_game: .game file -> .pdf"""

import os
from .lexer import tokenize
from .parser import Parser
from .codegen import Codegen
from pdf_writer.writer import PdfWriter, pdf_dict, pdf_stream
from pdf_writer.acroform import sprite_widget, label_widget, clickzone_widget
from pdf_writer.appearance import pixel_art_stream, solid_rect_stream

_ENGINE_PATH = os.path.join(os.path.dirname(__file__), "..", "engine", "engine.js")


def compile_game(source_path, output_path):
    with open(source_path) as f:
        source = f.read()

    tokens = tokenize(source)
    ast    = Parser(tokens).parse()
    gen    = Codegen(ast)
    logic  = gen.generate()

    cfg      = ast["config"]
    page_w   = int(cfg.get("width",  595))
    page_h   = int(cfg.get("height", 200))
    fps      = int(cfg.get("fps",    10))

    with open(_ENGINE_PATH) as f:
        engine_js = f.read()
    engine_js = engine_js.replace(
        "var PAGE_H = 0; /* INJECT:PAGE_H */",
        f"var PAGE_H = {page_h};"
    )

    # inject sprite frame counts so Engine.move handles multi-frame sprites
    sprites_map = "{" + ", ".join(
        f'"{sp["name"]}": {sp["frames"]}' for sp in gen.sprites
    ) + "}"
    engine_js = engine_js.replace(
        '_sprites: {}, /* INJECT:SPRITES - map of name -> frame count */',
        f'_sprites: {sprites_map},'
    )

    # inject sprite sizes so Engine.move uses correct w/h without reading field.rect
    sizes_map = "{" + ", ".join(
        f'"{sp["name"]}": {{w: {int(sp["w"])}, h: {int(sp["h"])}}}' for sp in gen.sprites
    ) + "}"
    engine_js = engine_js.replace(
        '_sizes:   {}, /* INJECT:SIZES   - map of name -> {w, h} in points */',
        f'_sizes: {sizes_map},'
    )

    # hide all non-primary frames at startup
    hide_frames = (
        "(function() {"
        " for (var sn in Engine._sprites) {"
        " var nf = Engine._sprites[sn];"
        " for (var fi = 1; fi < nf; fi++) {"
        " var f = _doc.getField('sprite_' + sn + '_' + fi);"
        " if (f) { f.display = display.hidden; }"
        " } } })();"
    )

    # guard: if Names/JavaScript AND OpenAction both fire, second run is a no-op
    bundled_js = (
        "if (typeof _pdfgame_loaded === 'undefined') {\n"
        "var _pdfgame_loaded = true;\n"
        + engine_js + "\n" + hide_frames + "\n" + logic
        + "\n}"
    )

    w = PdfWriter()
    catalog_id  = w.alloc_id()
    pages_id    = w.alloc_id()
    acroform_id = w.alloc_id()
    names_id    = w.alloc_id()
    page_id     = w.alloc_id()
    js_id       = w.alloc_id()

    w.add_object(js_id, pdf_stream(bundled_js, {"Subtype": "/JavaScript"}))

    # --- build sprite widgets ---
    field_ids = []
    for sp in gen.sprites:
        name   = sp["name"]
        frames = sp["frames"]
        sx, sy = int(sp["x"]), int(sp["y"])
        sw, sh = int(sp["w"]), int(sp["h"])

        src_sprite = next(s for s in ast["sprites"] if s["name"] == name)
        scale = src_sprite["scale"]

        for fi in range(frames):
            ap_id     = w.alloc_id()
            widget_id = w.alloc_id()

            pixel_frames = src_sprite["pixel_frames"]
            if pixel_frames and fi < len(pixel_frames):
                stream_bytes, fw, fh = pixel_art_stream(pixel_frames[fi], scale)
                w.add_object(ap_id, stream_bytes)
                sw, sh = int(fw), int(fh)
            else:
                w.add_object(ap_id, solid_rect_stream(sw, sh))

            field_name = f"{name}_{fi}" if frames > 1 else name
            w.add_object(widget_id, sprite_widget(
                widget_id, ap_id, field_name,
                x=sx, y=sy, w=sw, h=sh, page_h=page_h
            ))
            field_ids.append(widget_id)

    # --- build label widgets ---
    for lb in gen.labels:
        lbl_id = w.alloc_id()
        w.add_object(lbl_id, label_widget(
            lbl_id, lb["name"],
            x=int(lb["x"]), y=int(lb["y"]),
            w=int(lb["w"]), h=int(lb["h"]),
            value=lb["value"], page_h=page_h
        ))
        field_ids.append(lbl_id)

    # --- click zone (invisible, on top) ---
    zone_id = w.alloc_id()
    w.add_object(zone_id, clickzone_widget(
        zone_id, x=0, y=0, w=page_w, h=page_h, page_h=page_h
    ))
    field_ids.append(zone_id)

    # --- AcroForm ---
    fields = "[" + " ".join(f"{i} 0 R" for i in field_ids) + "]"
    dr = "<< /Font << /Helvetica << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >>"
    w.add_object(acroform_id, pdf_dict({"/Fields": fields, "/DR": dr}))

    # --- Names ---
    js_action = f"<< /S /JavaScript /JS {js_id} 0 R >>"
    w.add_object(names_id, pdf_dict({
        "/JavaScript": f"<< /Names [(gameScript) {js_action}] >>",
    }))

    # --- Catalog ---
    w.add_object(catalog_id, pdf_dict({
        "/Type":       "/Catalog",
        "/Pages":      f"{pages_id} 0 R",
        "/AcroForm":   f"{acroform_id} 0 R",
        "/Names":      f"{names_id} 0 R",
        "/OpenAction": js_action,
    }))

    w.add_object(pages_id, pdf_dict({
        "/Type": "/Pages", "/Kids": f"[{page_id} 0 R]", "/Count": "1",
    }))

    annots = "[" + " ".join(f"{i} 0 R" for i in field_ids) + "]"
    w.add_object(page_id, pdf_dict({
        "/Type":     "/Page",
        "/Parent":   f"{pages_id} 0 R",
        "/MediaBox": f"[0 0 {page_w} {page_h}]",
        "/Annots":   annots,
    }))

    w.write(output_path)
