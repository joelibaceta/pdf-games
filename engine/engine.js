/* PDF Game Engine - Acrobat JS (ES3) */
var _doc = this; // captured at script top level - in Acrobat doc context this IS the document

var Engine = (function () {
    var _intervalId = null;
    var PAGE_H = 0; /* INJECT:PAGE_H */

    function _pdfRect(gx, gy, w, h) {
        var py = PAGE_H - gy - h;
        return [gx, py, gx + w, py + h];
    }

    function _gamePos(f) {
        var r = f.rect;
        var w = r[2] - r[0];
        var h = r[3] - r[1];
        return { x: r[0], y: PAGE_H - r[3], w: w, h: h };
    }

    return {
        _updateFn: null,
        _sprites: {}, /* INJECT:SPRITES - map of name -> frame count */
        _sizes:   {}, /* INJECT:SIZES   - map of name -> {w, h} in points */
        _pos: {},     /* position registry: {name: {x,y,w,h}} in game coords */

        start: function (updateFn, fps) {
            if (_intervalId !== null) { return; } /* guard: only one interval */
            Engine._updateFn = updateFn;
            _intervalId = app.setInterval(
                "Engine._tick()", Math.round(1000 / fps)
            );
        },

        stop: function () {
            if (_intervalId !== null) {
                app.clearInterval(_intervalId);
                _intervalId = null;
            }
        },

        _tick: function () {
            if (Engine._updateFn) { Engine._updateFn(); }
        },

        _field: function (name) {
            var nf = Engine._sprites[name] || 1;
            var fname = nf > 1 ? "sprite_" + name + "_0" : "sprite_" + name;
            return _doc.getField(fname);
        },

        move: function (name, gx, gy) {
            var nf = Engine._sprites[name] || 1;
            var sz = Engine._sizes[name] || { w: 0, h: 0 };
            var posW = sz.w, posH = sz.h;
            for (var fi = 0; fi < nf; fi++) {
                var fname = nf > 1 ? "sprite_" + name + "_" + fi : "sprite_" + name;
                var f = _doc.getField(fname);
                if (!f) { continue; }
                f.rect = _pdfRect(gx, gy, posW, posH);
            }
            Engine._pos[name] = { x: gx, y: gy, w: posW, h: posH };
        },

        getPos: function (name) {
            if (Engine._pos[name]) { return Engine._pos[name]; }
            var f = Engine._field(name);
            if (!f) { return { x: 0, y: 0, w: 0, h: 0 }; }
            return _gamePos(f);
        },

        show: function (name) {
            var f = _doc.getField("sprite_" + name);
            if (f) { f.display = display.visible; }
        },

        hide: function (name) {
            var f = _doc.getField("sprite_" + name);
            if (f) { f.display = display.hidden; }
        },

        setText: function (name, val) {
            var f = _doc.getField("text_" + name);
            if (f) { f.value = "" + val; }
        },

        collides: function (a, b) {
            var pa = Engine.getPos(a);
            var pb = Engine.getPos(b);
            return !(
                pa.x + pa.w <= pb.x || pb.x + pb.w <= pa.x ||
                pa.y + pa.h <= pb.y || pb.y + pb.h <= pa.y
            );
        },

        random: function (min, max) {
            return Math.floor(Math.random() * (max - min + 1)) + min;
        },

        onInput: function (cb) { Engine._inputCb = cb; },

        triggerInput: function () {
            if (Engine._inputCb) { Engine._inputCb(); }
        },

        _inputCb: null
    };
})();
