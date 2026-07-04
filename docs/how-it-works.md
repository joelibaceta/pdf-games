# How it works — pdfgame

A deep dive into the `.game` language, the compiler, and the PDF engine internals.

---

## Table of contents

1. [The .game language](#the-game-language)
   - [game: section](#game-section)
   - [sprites: section](#sprites-section)
   - [labels: section](#labels-section)
   - [vars: section](#vars-section)
   - [Events: on start / update / click / restart](#events)
   - [Expressions and operators](#expressions-and-operators)
   - [Built-in functions](#built-in-functions)
2. [Writing your first game](#writing-your-first-game)
3. [Compiler internals](#compiler-internals)
   - [Lexer](#lexer)
   - [Parser](#parser)
   - [Codegen](#codegen)
   - [PDF Writer](#pdf-writer)
4. [Engine internals](#engine-internals)
   - [Shadow variables](#shadow-variables)
   - [Coordinate system](#coordinate-system)
   - [Collision detection](#collision-detection)

---

## The .game language

A `.game` file has five sections. All sections are optional except `game:`.

### game: section

```
game:
    title  = "My Game"
    width  = 500        # page width in points (1pt ≈ 0.35mm)
    height = 200        # page height in points
    fps    = 10         # target frame rate (practical max ~15 in Acrobat)
```

### sprites: section

Sprites are the visual elements. Each sprite becomes an AcroForm pushbutton widget field in the PDF. There are two kinds:

**Pixel art sprites** — defined with an `X`/`.` grid:

```
sprites:
    dino at (50, 117) scale 3:
        .........XXXX...
        ........XXXXXX..
        ........XXXXXX..
        .X.....XXXXXX...
        .XX..XXXXXXX....
        ..XXXXXXXX......
        ....XX.XX.......
        ....X...X.......
```

- `at (x, y)` — top-left position in game coordinates (pixels from top-left corner)
- `scale N` — each pixel in the grid becomes an N×N point square. Scale 3 → 3pt per pixel.
- Grid characters: `X` = black pixel, `.` = transparent. Only uppercase `X` is recognized.
- Sprite width/height in points = `grid_cols × scale` and `grid_rows × scale`.

**Solid fill sprites** — for backgrounds, floors, pipes:

```
sprites:
    floor  at (0, 165)    size (500, 4)   fill
    pipe   at (400, -150) size (40, 170)  fill
```

- `size (w, h)` — explicit dimensions in points.
- `fill` — renders as a solid black rectangle.
- Sprites can be positioned outside the page (negative y, or x > page width). Acrobat clips them to the MediaBox — useful for the Flappy Bird pipe trick.

**Multi-frame sprites** (animation):

```
sprites:
    runner at (50, 100) scale 2 frames 2:
        frame 0:
            .XXX.
            XXXXX
        frame 1:
            .XXX.
            XXXXX
```

All frames occupy the same position; the engine hides non-active frames. Use `Engine.frame(name, index)` to switch frames at runtime (not yet exposed in the DSL, planned).

### labels: section

Labels are read-only text fields. Use them for score, messages, game over text:

```
labels:
    score    at (390, 8)  size (100, 20) = "0"
    gameover at (110, 80) size (280, 30) = ""
```

- `at (x, y)` — top-left position
- `size (w, h)` — field dimensions
- `= "initial value"` — text shown at load time

Update labels at runtime with: `label_name.text = value`

### vars: section

User-defined game variables. Become JavaScript `var` declarations.

```
vars:
    vy     = 0
    speed  = 5
    alive  = true
    name   = "player"
```

Supported literal types: number (int or float), boolean (`true`/`false`), string (`"..."`).

Variables are global — accessible and assignable in any event handler.

### Events

Events are the game's logic. Each `on <name>:` block defines a function called by the engine.

```
on start:
    # runs once when the PDF loads, after the engine starts
    cactus.x = 480

on update:
    # runs every tick (controlled by fps)
    dino.y = dino.y + vy

on click:
    # runs when the player clicks anywhere on the page
    if dino.y >= 117:
        vy = -13

on restart:
    # called by restart() built-in; reset your game state here
    alive = true
    dino.y = 117
    score.text = "0"
```

### Expressions and operators

| Category | Operators |
|----------|-----------|
| Arithmetic | `+` `-` `*` `/` |
| Comparison | `==` `!=` `<` `>` `<=` `>=` |
| Logic | `and` `or` `not` |
| Grouping | `(` `)` |

**Reading sprite/label position:**

```
dino.x   # → _dino_x shadow variable (current x in game coords)
dino.y   # → _dino_y shadow variable (current y in game coords)
```

**Assigning sprite position:**

```
dino.y = dino.y + vy   # moves dino; calls Engine.move() automatically
```

**Assigning label text:**

```
score.text = points    # accepts numbers or strings
```

**Conditionals:**

```
if alive and dino.y >= 117:
    vy = 0

if not alive:
    return
```

**Return:**

`return` exits the current event handler immediately (useful inside nested ifs).

### Built-in functions

| Function | Description |
|----------|-------------|
| `collides(a, b)` | AABB collision between sprites `a` and `b`. Returns true/false. Uses a ≈16% inset on each side for tighter visual feel. |
| `random(min, max)` | Returns a random integer between `min` and `max` inclusive. |
| `restart()` | Calls the `on restart:` handler. |
| `show(name)` | Makes sprite visible. |
| `hide(name)` | Makes sprite invisible. |

---

## Writing your first game

Here's a minimal complete game — a ball bouncing left/right, click to reverse:

```
game:
    title  = "Bouncer"
    width  = 500
    height = 200
    fps    = 10

sprites:
    ball at (10, 95) size (10, 10) fill

vars:
    vx = 5

on update:
    ball.x = ball.x + vx
    if ball.x >= 490:
        vx = -5
    if ball.x <= 0:
        vx = 5

on click:
    vx = -vx
```

Build it:

```bash
python pdfgame.py build bouncer.game -o bouncer.pdf
```

Open in Acrobat. The ball moves. Click to reverse.

**Tips:**

- The page coordinate origin is **top-left** (y=0 is the top, y increases downward).
- Sprite positions are the **top-left corner** of the sprite bounding box.
- Gravity: increment `vy` each tick, apply it to `sprite.y`. Clamp when hitting the floor.
- For tighter collision feel: `collides()` already applies inset. For manual collision, use `sprite.x` and `sprite.y` in arithmetic expressions directly.
- Pipes/objects can start off-screen (negative y, x > page width) — Acrobat clips to the page.

---

## Compiler internals

The compiler lives in `compiler/` and has four stages:

### Lexer

`compiler/lexer.py` — converts source text to a flat token stream.

Key decisions:
- **Indentation is significant**: `INDENT`/`DEDENT` tokens are emitted for block structure, Python-style.
- **Pixel rows** are detected by `is_pixel_row(line)`: a line consisting entirely of `X` and `.` characters (no spaces). They emit a `TK_PIXEL_ROW` token and bypass the normal tokenizer.
- **Negative numbers** like `-150` are tokenized as a single `TK_NUMBER` token when the minus is directly followed by digits (no space). `sprite.y = -bvy` with a space uses unary minus from the parser.
- **Keywords** are resolved at token time: `true`, `false`, `and`, `or`, `not`, `if`, etc.

### Parser

`compiler/parser.py` — recursive descent parser. Produces a plain Python dict AST.

The AST structure:

```python
{
  "config": {"width": 500, "height": 200, "fps": 10},
  "sprites": [
    {"name": "dino", "x": 50, "y": 117, "scale": 3, "frames": 1,
     "pixel_frames": [["..XXXX..", ...]], "w": None, "h": None, "fill": False}
  ],
  "labels": [{"name": "score", "x": 390, "y": 8, "w": 100, "h": 20, "value": "0"}],
  "vars": {"vy": 0, "speed": 5, "alive": True},
  "events": {
    "update": [<stmt nodes>],
    "click":  [<stmt nodes>],
  }
}
```

Expression nodes:
- `{"kind": "num",   "value": 42}`
- `{"kind": "str",   "value": "hello"}`
- `{"kind": "bool",  "value": True}`
- `{"kind": "var",   "name": "speed"}`
- `{"kind": "prop",  "obj": "dino", "prop": "y"}`
- `{"kind": "binop", "op": "+", "left": ..., "right": ...}`
- `{"kind": "unop",  "op": "-", "operand": ...}`
- `{"kind": "call",  "name": "collides", "args": [...]}`

Statement nodes:
- `{"kind": "assign", "target": <expr>, "value": <expr>}`
- `{"kind": "if",     "cond": <expr>, "then": [...], "else_": [...]}`
- `{"kind": "return"}`
- `{"kind": "expr_stmt", "expr": <expr>}`

### Codegen

`compiler/codegen.py` — walks the AST and emits JavaScript source.

**Shadow variables**: for every sprite `name`, the codegen emits:

```javascript
var _name_x = <initial_x>;
var _name_y = <initial_y>;
```

When a sprite property is assigned (`dino.y = expr`), the codegen emits:

```javascript
_dino_y = <expr>;
Engine.move("dino", _dino_x, _dino_y);
```

This keeps shadow vars in sync with the engine's internal position map, enabling AABB collision without reading `field.rect` (which has inconsistent coordinate conventions across Acrobat versions).

**Inline AABB collision**: `collides(a, b)` expands to a fully inlined expression using shadow variables — no function call, no field.rect read:

```javascript
(_a_x + ai < (_b_x + bw - bi) && _b_x + bi < (_a_x + aw - ai)
 && _a_y < (_b_y + bh) && _b_y < (_a_y + ah))
```

Where `ai` and `bi` are per-sprite insets: `max(3, sprite_width // 6)`.

**Sizes injection**: the compiler injects a `_sizes` map into the engine at build time so `Engine.move()` uses compile-time sprite dimensions rather than reading `field.rect`:

```javascript
Engine._sizes = {"dino": {w: 48, h: 48}, "cactus1": {w: 24, h: 24}};
```

### PDF Writer

`pdf_writer/writer.py` + `pdf_writer/appearance.py` + `pdf_writer/acroform.py`

Generates a valid PDF file from raw bytes with no external dependencies.

**Object model**: every PDF object (Catalog, Pages, Page, AcroForm, fields, streams) gets an allocated ID. The writer tracks byte offsets to build the cross-reference table at the end.

**Sprite widgets** (`pdf_writer/acroform.py:sprite_widget`): each sprite is a `/Type /Annot /Subtype /Widget /FT /Btn` (pushbutton) field. Its appearance (`/AP /N`) is a Form XObject stream containing the pixel-drawing commands.

**Appearance streams** (`pdf_writer/appearance.py:pixel_art_stream`): iterates the pixel grid row by row (Y-flipped, since PDF Y is bottom-up), emits one `x y scale scale re` command per `X` pixel, then a single `f` to fill all rectangles.

**Coordinate flip**: game coordinates (top-left origin, Y-down) are converted to PDF coordinates (bottom-left origin, Y-up) with:

```python
pdf_y = PAGE_H - game_y - sprite_height
```

**JavaScript injection**: the bundled JS (engine + game logic) is embedded as a `/JavaScript` stream, referenced both in the `/Names` tree (doc-level JS) and as the `/OpenAction`, for maximum Acrobat compatibility. A `_pdfgame_loaded` guard prevents double-execution.

---

## Engine internals

`engine/engine.js` — runs inside Acrobat. ES3-compatible (no `let`, no `const`, no arrow functions, no template literals).

### Shadow variables

The engine maintains `Engine._pos[name]` — a position registry updated on every `Engine.move()` call. This is the authoritative position for collision detection, avoiding the need to read `field.rect`.

```javascript
Engine.move = function(name, gx, gy) {
    var sz = Engine._sizes[name];          // injected at compile time
    for (var fi = 0; fi < nf; fi++) {
        var f = _doc.getField(fname);
        f.rect = _pdfRect(gx, gy, sz.w, sz.h);
    }
    Engine._pos[name] = {x: gx, y: gy, w: sz.w, h: sz.h};
};
```

### Coordinate system

```
game coords:          PDF coords:
(0,0)──────→ x        y ↑
  │                     │
  ↓ y              (0,0)──────→ x
```

Conversion: `pdf_rect = [gx, PAGE_H - gy - h, gx + w, PAGE_H - gy]`

### Collision detection

`collides(a, b)` in the DSL compiles to an inline AABB check. No function call overhead. Shadow variables are read directly:

```javascript
// collides(bird, pipe_top) expands to:
(_bird_x + 4 < (_pipe_top_x + 40 - 6)
 && _pipe_top_x + 6 < (_bird_x + 24 - 4)
 && _bird_y < (_pipe_top_y + 170)
 && _pipe_top_y < (_bird_y + 24))
```

The horizontal inset (`ai = max(3, width // 6)`) shrinks the effective hitbox so collision triggers only when sprites visually overlap, not just when bounding boxes touch.
