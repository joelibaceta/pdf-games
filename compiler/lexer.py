import re

# Token types
TK_SECTION   = "SECTION"    # game, sprites, labels, vars, on
TK_EVENT     = "EVENT"      # start, update, click, restart (after 'on')
TK_NAME      = "NAME"       # identifiers
TK_STRING    = "STRING"     # "text"
TK_NUMBER    = "NUMBER"     # 42, 3.14
TK_BOOL      = "BOOL"       # true, false
TK_AT        = "AT"         # at
TK_SIZE      = "SIZE"       # size
TK_SCALE     = "SCALE"      # scale
TK_FRAMES    = "FRAMES"     # frames
TK_FRAME     = "FRAME"      # frame
TK_FILL      = "FILL"       # fill
TK_COLOR     = "COLOR"      # color
TK_FROM      = "FROM"       # from
TK_EQ        = "EQ"         # =
TK_LPAREN    = "LPAREN"     # (
TK_RPAREN    = "RPAREN"     # )
TK_COMMA     = "COMMA"      # ,
TK_DOT       = "DOT"        # .
TK_COLON     = "COLON"      # :
TK_OP        = "OP"         # + - * / >= <= > < == !=
TK_NOT       = "NOT"        # not
TK_AND       = "AND"        # and
TK_OR        = "OR"         # or
TK_IF        = "IF"         # if
TK_ELSE      = "ELSE"       # else
TK_RETURN    = "RETURN"     # return
TK_PIXEL_ROW = "PIXEL_ROW"  # line of X/. (sprite pixel art)
TK_INDENT    = "INDENT"
TK_DEDENT    = "DEDENT"
TK_NEWLINE   = "NEWLINE"
TK_EOF       = "EOF"

KEYWORDS = {
    "game": TK_SECTION, "sprites": TK_SECTION, "labels": TK_SECTION,
    "vars": TK_SECTION, "on": TK_SECTION,
    "start": TK_EVENT, "update": TK_EVENT, "click": TK_EVENT, "restart": TK_EVENT,
    "at": TK_AT, "size": TK_SIZE, "scale": TK_SCALE,
    "frames": TK_FRAMES, "frame": TK_FRAME, "fill": TK_FILL,
    "color": TK_COLOR, "from": TK_FROM,
    "not": TK_NOT, "and": TK_AND, "or": TK_OR,
    "if": TK_IF, "else": TK_ELSE, "return": TK_RETURN,
    "true": TK_BOOL, "false": TK_BOOL,
}


class Token:
    def __init__(self, kind, value, line):
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


def is_pixel_row(s):
    """A line of only X and . characters (at least one, no spaces)."""
    return len(s) > 0 and all(c in "X." for c in s)


def tokenize(source):
    lines = source.splitlines()
    tokens = []
    indent_stack = [0]

    for lineno, raw_line in enumerate(lines, 1):
        # strip trailing whitespace, keep leading
        line = raw_line.rstrip()

        # blank lines and comments
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue

        # measure indent
        indent = len(line) - len(stripped)

        # emit INDENT / DEDENT first (before any content check)
        current = indent_stack[-1]
        if indent > current:
            indent_stack.append(indent)
            tokens.append(Token(TK_INDENT, indent, lineno))
        while indent < indent_stack[-1]:
            indent_stack.pop()
            tokens.append(Token(TK_DEDENT, indent_stack[-1], lineno))

        # pixel art rows: emit and skip content tokenization
        if is_pixel_row(stripped):
            tokens.append(Token(TK_PIXEL_ROW, stripped, lineno))
            tokens.append(Token(TK_NEWLINE, None, lineno))
            continue

        # tokenize the content of the line
        pos = 0
        content = stripped
        while pos < len(content):
            # skip spaces
            if content[pos] == " ":
                pos += 1
                continue

            # comment
            if content[pos] == "#":
                break

            # string
            if content[pos] == '"':
                end = content.index('"', pos + 1)
                tokens.append(Token(TK_STRING, content[pos+1:end], lineno))
                pos = end + 1
                continue

            # number
            m = re.match(r"-?\d+(\.\d+)?", content[pos:])
            if m:
                val = float(m.group()) if "." in m.group() else int(m.group())
                tokens.append(Token(TK_NUMBER, val, lineno))
                pos += len(m.group())
                continue

            # two-char operators
            two = content[pos:pos+2]
            if two in (">=", "<=", "==", "!="):
                tokens.append(Token(TK_OP, two, lineno))
                pos += 2
                continue

            # single-char tokens
            ch = content[pos]
            simple = {
                "=": TK_EQ, "(": TK_LPAREN, ")": TK_RPAREN,
                ",": TK_COMMA, ".": TK_DOT, ":": TK_COLON,
                "+": TK_OP, "-": TK_OP, "*": TK_OP, "/": TK_OP,
                ">": TK_OP, "<": TK_OP,
            }
            if ch in simple:
                tokens.append(Token(simple[ch], ch, lineno))
                pos += 1
                continue

            # identifier / keyword
            m = re.match(r"[a-zA-Z_][a-zA-Z0-9_]*", content[pos:])
            if m:
                word = m.group()
                kind = KEYWORDS.get(word, TK_NAME)
                tokens.append(Token(kind, word, lineno))
                pos += len(word)
                continue

            raise SyntaxError(f"Unexpected char {content[pos]!r} at line {lineno}")

        tokens.append(Token(TK_NEWLINE, None, lineno))

    # close any open indents
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token(TK_DEDENT, 0, 0))

    tokens.append(Token(TK_EOF, None, 0))
    return tokens
