class PdfWriter:
    def __init__(self):
        self._objects = []  # list of (obj_id, bytes)
        self._offsets = []
        self._next_id = 1

    def alloc_id(self):
        oid = self._next_id
        self._next_id += 1
        return oid

    def add_object(self, oid, content):
        """content: bytes or str"""
        if isinstance(content, str):
            content = content.encode()
        self._objects.append((oid, content))

    def write(self, path):
        out = bytearray()
        out += b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"

        offsets = {}
        for oid, content in sorted(self._objects):
            offsets[oid] = len(out)
            out += f"{oid} 0 obj\n".encode()
            out += content
            out += b"\nendobj\n"

        xref_offset = len(out)
        count = max(offsets) + 1
        out += f"xref\n0 {count}\n".encode()
        out += b"0000000000 65535 f \n"
        for i in range(1, count):
            off = offsets.get(i, 0)
            out += f"{off:010d} 00000 n \n".encode()

        out += b"trailer\n"
        out += f"<< /Size {count} /Root 1 0 R >>\n".encode()
        out += f"startxref\n{xref_offset}\n%%EOF\n".encode()

        with open(path, "wb") as f:
            f.write(out)


def pdf_dict(d):
    parts = ["<<"]
    for k, v in d.items():
        parts.append(f"  {k} {v}")
    parts.append(">>")
    return "\n".join(parts)


def pdf_stream(data, extra=None):
    if isinstance(data, str):
        data = data.encode()
    d = {"Length": len(data)}
    if extra:
        d.update(extra)
    header = pdf_dict({f"/{k}": v for k, v in d.items()})
    return f"{header}\nstream\n".encode() + data + b"\nendstream"
