from .lexer import (
    TK_SECTION, TK_EVENT, TK_NAME, TK_STRING, TK_NUMBER, TK_BOOL,
    TK_AT, TK_SIZE, TK_SCALE, TK_FRAMES, TK_FRAME, TK_FILL,
    TK_EQ, TK_LPAREN, TK_RPAREN, TK_COMMA, TK_DOT, TK_COLON, TK_OP,
    TK_NOT, TK_AND, TK_OR, TK_IF, TK_ELSE, TK_RETURN,
    TK_PIXEL_ROW, TK_INDENT, TK_DEDENT, TK_NEWLINE, TK_EOF,
)

# AST node helpers
def node(kind, **kw): return {"kind": kind, **kw}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self): return self.tokens[self.pos]
    def peek_kind(self): return self.tokens[self.pos].kind
    def peek_value(self): return self.tokens[self.pos].value

    def consume(self, kind=None, value=None):
        tok = self.tokens[self.pos]
        if kind and tok.kind != kind:
            raise SyntaxError(f"Expected {kind}, got {tok.kind}({tok.value!r}) at line {tok.line}")
        if value and tok.value != value:
            raise SyntaxError(f"Expected {value!r}, got {tok.value!r} at line {tok.line}")
        self.pos += 1
        return tok

    def skip_newlines(self):
        while self.peek_kind() == TK_NEWLINE:
            self.pos += 1

    def parse(self):
        game = {"config": {}, "sprites": [], "labels": [], "vars": {}, "events": {}}
        self.skip_newlines()
        while self.peek_kind() != TK_EOF:
            tok = self.peek()
            if tok.kind == TK_SECTION:
                if tok.value == "game":
                    self.parse_game_section(game)
                elif tok.value == "sprites":
                    self.parse_sprites_section(game)
                elif tok.value == "labels":
                    self.parse_labels_section(game)
                elif tok.value == "vars":
                    self.parse_vars_section(game)
                elif tok.value == "on":
                    self.parse_event_section(game)
                else:
                    self.pos += 1
            else:
                self.pos += 1
        return game

    # --- game: section ---

    def parse_game_section(self, game):
        self.consume(TK_SECTION, "game")
        self.consume(TK_COLON)
        self.consume(TK_NEWLINE)
        self.consume(TK_INDENT)
        while self.peek_kind() not in (TK_DEDENT, TK_EOF):
            if self.peek_kind() == TK_NEWLINE:
                self.pos += 1; continue
            name = self.consume(TK_NAME).value
            self.consume(TK_EQ)
            val = self.parse_literal()
            game["config"][name] = val
            self.skip_newlines()
        if self.peek_kind() == TK_DEDENT: self.pos += 1

    # --- sprites: section ---

    def parse_sprites_section(self, game):
        self.consume(TK_SECTION, "sprites")
        self.consume(TK_COLON)
        self.consume(TK_NEWLINE)
        self.consume(TK_INDENT)
        while self.peek_kind() not in (TK_DEDENT, TK_EOF):
            if self.peek_kind() == TK_NEWLINE:
                self.pos += 1; continue
            game["sprites"].append(self.parse_sprite_def())
        if self.peek_kind() == TK_DEDENT: self.pos += 1

    def parse_sprite_def(self):
        name = self.consume(TK_NAME).value
        x, y, w, h, scale, frames, fill = 0, 0, None, None, 4, 1, False
        pixel_frames = []

        while self.peek_kind() not in (TK_NEWLINE, TK_COLON, TK_EOF, TK_DEDENT):
            k = self.peek_kind()
            if k == TK_AT:
                self.pos += 1
                x, y = self.parse_pair()
            elif k == TK_SIZE:
                self.pos += 1
                w, h = self.parse_pair()
            elif k == TK_SCALE:
                self.pos += 1
                scale = self.consume(TK_NUMBER).value
            elif k == TK_FRAMES:
                self.pos += 1
                frames = self.consume(TK_NUMBER).value
            elif k == TK_FILL:
                self.pos += 1; fill = True
            else:
                self.pos += 1

        if self.peek_kind() == TK_COLON:
            self.consume(TK_COLON)
            self.skip_newlines()
            if self.peek_kind() == TK_INDENT:
                self.consume(TK_INDENT)
                pixel_frames = self.parse_pixel_frames()
                if self.peek_kind() == TK_DEDENT: self.pos += 1
            elif self.peek_kind() == TK_PIXEL_ROW:
                # pixel rows at same indent level (rare but valid)
                pixel_frames = self.parse_pixel_frames()
        else:
            self.skip_newlines()

        return node("sprite", name=name, x=x, y=y, w=w, h=h,
                    scale=int(scale), frames=int(frames), fill=fill,
                    pixel_frames=pixel_frames)

    def parse_pixel_frames(self):
        frames = []
        while self.peek_kind() not in (TK_DEDENT, TK_EOF):
            if self.peek_kind() == TK_NEWLINE:
                self.pos += 1; continue
            if self.peek_kind() == TK_FRAME:
                # explicit "frame N:" header — pixel rows are indented inside
                self.consume(TK_FRAME)
                self.consume(TK_NUMBER)
                self.consume(TK_COLON)
                self.skip_newlines()
                rows = []
                if self.peek_kind() == TK_INDENT:
                    self.consume(TK_INDENT)
                    while self.peek_kind() in (TK_PIXEL_ROW, TK_NEWLINE):
                        if self.peek_kind() == TK_NEWLINE: self.pos += 1; continue
                        rows.append(self.consume(TK_PIXEL_ROW).value)
                        self.skip_newlines()
                    if self.peek_kind() == TK_DEDENT: self.pos += 1
                frames.append(rows)
            elif self.peek_kind() == TK_PIXEL_ROW:
                # implicit single frame — no "frame N:" header
                rows = []
                while self.peek_kind() in (TK_PIXEL_ROW, TK_NEWLINE):
                    if self.peek_kind() == TK_NEWLINE: self.pos += 1; continue
                    rows.append(self.consume(TK_PIXEL_ROW).value)
                    self.skip_newlines()
                frames.append(rows)
                break
            else:
                break
        return frames

    # --- labels: section ---

    def parse_labels_section(self, game):
        self.consume(TK_SECTION, "labels")
        self.consume(TK_COLON)
        self.consume(TK_NEWLINE)
        self.consume(TK_INDENT)
        while self.peek_kind() not in (TK_DEDENT, TK_EOF):
            if self.peek_kind() == TK_NEWLINE:
                self.pos += 1; continue
            name = self.consume(TK_NAME).value
            x, y, w, h = 0, 0, 100, 20
            while self.peek_kind() not in (TK_EQ, TK_NEWLINE, TK_EOF):
                k = self.peek_kind()
                if k == TK_AT: self.pos += 1; x, y = self.parse_pair()
                elif k == TK_SIZE: self.pos += 1; w, h = self.parse_pair()
                else: self.pos += 1
            value = ""
            if self.peek_kind() == TK_EQ:
                self.consume(TK_EQ)
                value = self.consume(TK_STRING).value
            self.skip_newlines()
            game["labels"].append(node("label", name=name, x=x, y=y, w=w, h=h, value=value))
        if self.peek_kind() == TK_DEDENT: self.pos += 1

    # --- vars: section ---

    def parse_vars_section(self, game):
        self.consume(TK_SECTION, "vars")
        self.consume(TK_COLON)
        self.consume(TK_NEWLINE)
        self.consume(TK_INDENT)
        while self.peek_kind() not in (TK_DEDENT, TK_EOF):
            if self.peek_kind() == TK_NEWLINE:
                self.pos += 1; continue
            name = self.consume(TK_NAME).value
            self.consume(TK_EQ)
            val = self.parse_literal()
            game["vars"][name] = val
            self.skip_newlines()
        if self.peek_kind() == TK_DEDENT: self.pos += 1

    # --- on <event>: section ---

    def parse_event_section(self, game):
        self.consume(TK_SECTION, "on")
        event = self.consume().value  # start / update / click / restart
        self.consume(TK_COLON)
        self.consume(TK_NEWLINE)
        stmts = []
        if self.peek_kind() == TK_INDENT:
            self.consume(TK_INDENT)
            stmts = self.parse_block()
            if self.peek_kind() == TK_DEDENT: self.pos += 1
        game["events"][event] = stmts

    # --- statement parsing ---

    def parse_block(self):
        stmts = []
        while self.peek_kind() not in (TK_DEDENT, TK_EOF):
            if self.peek_kind() == TK_NEWLINE:
                self.pos += 1; continue
            stmts.append(self.parse_stmt())
        return stmts

    def parse_stmt(self):
        k = self.peek_kind()

        if k == TK_RETURN:
            self.consume(TK_RETURN); self.skip_newlines()
            return node("return")

        if k == TK_IF:
            return self.parse_if()

        # assignment or call
        # peek ahead: NAME DOT NAME EQ  |  NAME EQ  |  NAME LPAREN  |  NAME DOT NAME LPAREN
        expr = self.parse_expr()
        if self.peek_kind() == TK_EQ:
            self.consume(TK_EQ)
            value = self.parse_expr()
            self.skip_newlines()
            return node("assign", target=expr, value=value)

        self.skip_newlines()
        return node("expr_stmt", expr=expr)

    def parse_if(self):
        self.consume(TK_IF)
        cond = self.parse_expr()
        self.consume(TK_COLON)
        self.skip_newlines()
        then = []
        else_ = []
        if self.peek_kind() == TK_INDENT:
            self.consume(TK_INDENT)
            then = self.parse_block()
            if self.peek_kind() == TK_DEDENT: self.pos += 1
        self.skip_newlines()
        if self.peek_kind() == TK_ELSE:
            self.consume(TK_ELSE)
            self.consume(TK_COLON)
            self.skip_newlines()
            if self.peek_kind() == TK_INDENT:
                self.consume(TK_INDENT)
                else_ = self.parse_block()
                if self.peek_kind() == TK_DEDENT: self.pos += 1
        return node("if", cond=cond, then=then, else_=else_)

    # --- expression parsing (recursive descent) ---

    def parse_expr(self): return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek_kind() == TK_OR:
            self.pos += 1
            left = node("binop", op="||", left=left, right=self.parse_and())
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek_kind() == TK_AND:
            self.pos += 1
            left = node("binop", op="&&", left=left, right=self.parse_not())
        return left

    def parse_not(self):
        if self.peek_kind() == TK_NOT:
            self.pos += 1
            return node("unop", op="!", operand=self.parse_not())
        return self.parse_cmp()

    def parse_cmp(self):
        left = self.parse_add()
        while self.peek_kind() == TK_OP and self.peek_value() in (">=", "<=", ">", "<", "==", "!="):
            op = self.consume(TK_OP).value
            left = node("binop", op=op, left=left, right=self.parse_add())
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek_kind() == TK_OP and self.peek_value() in ("+", "-"):
            op = self.consume(TK_OP).value
            left = node("binop", op=op, left=left, right=self.parse_mul())
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.peek_kind() == TK_OP and self.peek_value() in ("*", "/"):
            op = self.consume(TK_OP).value
            left = node("binop", op=op, left=left, right=self.parse_unary())
        return left

    def parse_unary(self):
        if self.peek_kind() == TK_OP and self.peek_value() == "-":
            self.pos += 1
            return node("unop", op="-", operand=self.parse_primary())
        return self.parse_primary()

    def parse_primary(self):
        k = self.peek_kind()

        if k == TK_NUMBER:
            return node("num", value=self.consume().value)
        if k == TK_STRING:
            return node("str", value=self.consume().value)
        if k == TK_BOOL:
            return node("bool", value=self.consume().value == "true")

        if k == TK_LPAREN:
            self.consume(TK_LPAREN)
            e = self.parse_expr()
            self.consume(TK_RPAREN)
            return e

        if k in (TK_NAME, TK_EVENT):
            name = self.consume().value
            # property access or call
            if self.peek_kind() == TK_DOT:
                self.consume(TK_DOT)
                prop = self.consume(TK_NAME).value
                return node("prop", obj=name, prop=prop)
            if self.peek_kind() == TK_LPAREN:
                self.consume(TK_LPAREN)
                args = []
                while self.peek_kind() != TK_RPAREN:
                    args.append(self.parse_expr())
                    if self.peek_kind() == TK_COMMA: self.pos += 1
                self.consume(TK_RPAREN)
                return node("call", name=name, args=args)
            return node("var", name=name)

        raise SyntaxError(f"Unexpected token {self.peek()} in expression")

    # --- helpers ---

    def parse_pair(self):
        self.consume(TK_LPAREN)
        a = self.consume(TK_NUMBER).value
        self.consume(TK_COMMA)
        b = self.consume(TK_NUMBER).value
        self.consume(TK_RPAREN)
        return a, b

    def parse_literal(self):
        k = self.peek_kind()
        if k == TK_NUMBER: return self.consume().value
        if k == TK_STRING: return self.consume().value
        if k == TK_BOOL:   return self.consume().value == "true"
        raise SyntaxError(f"Expected literal, got {self.peek()}")
