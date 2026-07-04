"""AST -> JavaScript source + GameDef (sprite/label metadata for PDF builder)."""


# --- GameDef dataclasses (plain dicts) ---

def make_sprite(name, x, y, w, h, frames=1):
    return {"name": name, "x": x, "y": y, "w": w, "h": h, "frames": frames}

def make_label(name, x, y, w, h, value=""):
    return {"name": name, "x": x, "y": y, "w": w, "h": h, "value": value}


# --- JS code generator ---

class Codegen:
    def __init__(self, ast):
        self.ast = ast
        self.sprites = []    # GameDef sprite entries
        self.labels  = []    # GameDef label entries
        self._lines  = []    # generated JS lines

    def generate(self):
        cfg     = self.ast["config"]
        sprites = self.ast["sprites"]
        labels  = self.ast["labels"]
        vars_   = self.ast["vars"]
        events  = self.ast["events"]

        # --- sprite metadata + shadow vars ---
        for sp in sprites:
            name  = sp["name"]
            x, y  = sp["x"], sp["y"]
            scale = sp["scale"]
            nframes = sp["frames"]

            if sp["pixel_frames"]:
                rows = sp["pixel_frames"][0]
                w_px = max(len(r) for r in rows)
                h_px = len(rows)
                w = w_px * scale
                h = h_px * scale
            elif sp["w"] is not None:
                w, h = sp["w"], sp["h"]
            else:
                w, h = scale * 8, scale * 8

            actual_frames = max(nframes, len(sp["pixel_frames"]))
            self.sprites.append(make_sprite(name, x, y, w, h, actual_frames))

            self._emit(f"var _{name}_x = {x};")
            self._emit(f"var _{name}_y = {y};")

        # --- label metadata ---
        for lb in labels:
            self.labels.append(make_label(
                lb["name"], lb["x"], lb["y"], lb["w"], lb["h"], lb["value"]
            ))

        # --- user vars ---
        for vname, vval in vars_.items():
            js_val = self._js_literal(vval)
            self._emit(f"var {vname} = {js_val};")

        # --- event handlers ---
        for event_name, stmts in events.items():
            fn_name = f"_on_{event_name}"
            self._emit(f"\nfunction {fn_name}() {{")
            for stmt in stmts:
                for line in self._stmt(stmt):
                    self._emit("    " + line)
            self._emit("}")

        # --- wire up engine ---
        self._emit("\nEngine.onInput(function () {")
        click_fn = "_on_click" if "click" in events else "null"
        self._emit(f"    if (typeof {click_fn} === 'function') {{ {click_fn}(); }}")
        self._emit("});")

        update_fn = "_on_update" if "update" in events else "function(){}"
        self._emit(f"\nEngine.start({update_fn}, {cfg.get('fps', 10)});")

        if "start" in events:
            self._emit("\n_on_start();")

        return "\n".join(self._lines)

    def _emit(self, line):
        self._lines.append(line)

    # --- statement -> list of JS lines ---

    def _stmt(self, s):
        k = s["kind"]
        if k == "return":
            return ["return;"]
        if k == "if":
            return self._if(s)
        if k == "assign":
            return self._assign(s)
        if k == "expr_stmt":
            return [self._expr(s["expr"]) + ";"]
        return [f"/* unknown stmt {k} */"]

    def _assign(self, s):
        target = s["target"]
        val    = self._expr(s["value"])
        lines  = []

        if target["kind"] == "prop":
            obj, prop = target["obj"], target["prop"]
            if prop == "text":
                lines.append(f'Engine.setText("{obj}", {val});')
            elif prop in ("x", "y"):
                # update shadow var, then sync position
                lines.append(f"_{obj}_{prop} = {val};")
                lines.append(f'Engine.move("{obj}", _{obj}_x, _{obj}_y);')
            else:
                lines.append(f"/* unsupported prop {obj}.{prop} */")
        elif target["kind"] == "var":
            lines.append(f"{target['name']} = {val};")
        return lines

    def _if(self, s):
        lines = [f"if ({self._expr(s['cond'])}) {{"]
        for stmt in s["then"]:
            for l in self._stmt(stmt):
                lines.append("    " + l)
        if s["else_"]:
            lines.append("} else {")
            for stmt in s["else_"]:
                for l in self._stmt(stmt):
                    lines.append("    " + l)
        lines.append("}")
        return lines

    # --- expression -> JS string ---

    def _expr(self, e):
        k = e["kind"]
        if k == "num":   return str(e["value"])
        if k == "str":   return f'"{e["value"]}"'
        if k == "bool":  return "true" if e["value"] else "false"
        if k == "var":   return e["name"]

        if k == "prop":
            obj, prop = e["obj"], e["prop"]
            if prop in ("x", "y"):
                return f"_{obj}_{prop}"
            return f"/* {obj}.{prop} */"

        if k == "unop":
            return f"({e['op']}{self._expr(e['operand'])})"

        if k == "binop":
            return f"({self._expr(e['left'])} {e['op']} {self._expr(e['right'])})"

        if k == "call":
            args = ", ".join(self._expr(a) for a in e["args"])
            name = e["name"]
            # built-in mappings
            builtins = {
                "collides": lambda: self._inline_collides(e["args"][0]["name"], e["args"][1]["name"]),
                "random":   lambda: f"Engine.random({args})",
                "show":     lambda: f'Engine.show("{e["args"][0]["name"]}")',
                "hide":     lambda: f'Engine.hide("{e["args"][0]["name"]}")',
                "frame":    lambda: f'Engine.frame("{e["args"][0]["name"]}", {self._expr(e["args"][1])})',
                "game_over":lambda: f'Engine.gameOver({args})',
                "restart":  lambda: "_on_restart()",
            }
            if name in builtins:
                return builtins[name]()
            return f"{name}({args})"

        return f"/* unknown expr {k} */"

    def _inline_collides(self, a_name, b_name):
        """AABB collision using shadow variables — no field rect roundtrip.
        Applies a 1/6 inset on each horizontal side for tighter visual collision."""
        a = next((s for s in self.sprites if s["name"] == a_name), None)
        b = next((s for s in self.sprites if s["name"] == b_name), None)
        if not a or not b:
            return "false"
        aw, ah = int(a["w"]), int(a["h"])
        bw, bh = int(b["w"]), int(b["h"])
        ai = max(3, aw // 6)  # inset for a (~16% of width)
        bi = max(3, bw // 6)  # inset for b (~16% of width)
        return (
            f"(_{a_name}_x + {ai} < (_{b_name}_x + {bw} - {bi})"
            f" && _{b_name}_x + {bi} < (_{a_name}_x + {aw} - {ai})"
            f" && _{a_name}_y < (_{b_name}_y + {bh})"
            f" && _{b_name}_y < (_{a_name}_y + {ah}))"
        )

    def _js_literal(self, v):
        if isinstance(v, bool): return "true" if v else "false"
        if isinstance(v, str):  return f'"{v}"'
        return str(v)
