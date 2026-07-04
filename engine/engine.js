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

        start: function (updateFn, fps) {
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

        move: function (name, gx, gy) {
            var f = _doc.getField("sprite_" + name);
            if (!f) { return; }
            var r = f.rect;
            var w = r[2] - r[0];
            var h = r[3] - r[1];
            f.rect = _pdfRect(gx, gy, w, h);
        },

        getPos: function (name) {
            var f = _doc.getField("sprite_" + name);
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
