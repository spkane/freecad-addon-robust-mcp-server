"""Build the common FreeCAD-side object inspection program.

The program runs inside FreeCAD, which need not have the MCP package installed.
Keeping it here ensures all bridge modes apply the same wire-safe conversion.
"""

_INSPECTION_PROGRAM = r"""
import math

doc = FreeCAD.ActiveDocument if _doc_name is None else FreeCAD.getDocument(_doc_name)
if doc is None:
    raise ValueError("No document found")
obj = doc.getObject(_obj_name)
if obj is None:
    raise ValueError("Object not found: " + _obj_name)

# XML-RPC accepts only 32-bit integers and XML 1.0 text. Use the same
# representation for every transport and bound the work and output size.
_remaining_nodes = [512]
_remaining_chars = [2048]
_max_items = 100
_max_depth = 8

def _xml_text(value):
    return "".join(
        char if (ord(char) in (9, 10, 13) or 32 <= ord(char) <= 0xD7FF
                 or 0xE000 <= ord(char) <= 0xFFFD
                 or 0x10000 <= ord(char) <= 0x10FFFF) else "\uFFFD"
        for char in str(value)
    )

def _text(value):
    value = str(value)
    limit = min(512, _remaining_chars[0])
    truncated = len(value) > limit
    value = value[:limit]
    _remaining_chars[0] -= len(value)
    value = _xml_text(value)
    return value + ("<truncated>" if truncated else "")

def _mark_truncated(mapping):
    key = "<truncated>"
    while key in mapping:
        key += "_"
    mapping[key] = True

def _safe(value, depth=0, active=None):
    if _remaining_nodes[0] <= 0:
        return "<truncated>"
    _remaining_nodes[0] -= 1
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value if -(2**31) <= value < 2**31 else _text(value)
    if type(value) is float:
        return value if math.isfinite(value) else _text(value)
    if type(value) is str:
        return _text(value)
    if depth >= _max_depth:
        return "<max depth>"
    if active is None:
        active = set()
    if type(value) in (list, tuple, dict):
        identity = id(value)
        if identity in active:
            return "<cycle>"
        active.add(identity)
        try:
            if type(value) is dict:
                result = {}
                for index, (key, item) in enumerate(value.items()):
                    if index >= _max_items or _remaining_nodes[0] <= 0 or _remaining_chars[0] <= 0:
                        _mark_truncated(result)
                        break
                    safe_key = _text(key)
                    if safe_key in result:
                        _mark_truncated(result)
                        break
                    result[safe_key] = _safe(item, depth + 1, active)
                return result
            result = []
            for index, item in enumerate(value):
                if index >= _max_items or _remaining_nodes[0] <= 0 or _remaining_chars[0] <= 0:
                    result.append("<truncated>")
                    break
                result.append(_safe(item, depth + 1, active))
            return result
        finally:
            active.remove(identity)
    try:
        if value.isDerivedFrom("App::DocumentObject"):
            linked_doc = value.Document
            return {
                "name": _text(value.Name),
                "label": _text(value.Label),
                "type_id": _text(value.TypeId),
                "document": _text(linked_doc.Name) if linked_doc else None,
            }
    except (AttributeError, TypeError):
        pass
    return _text(value)

props = {}
if _include_properties:
    for index, prop in enumerate(obj.PropertiesList):
        if index >= _max_items or _remaining_nodes[0] <= 0 or _remaining_chars[0] <= 0:
            _mark_truncated(props)
            break
        try:
            key = _text(prop)
            if key != prop or key in props:
                _mark_truncated(props)
                break
            props[key] = _safe(getattr(obj, prop))
        except Exception:
            props[prop] = "<unreadable>"

shape_info = None
if _include_shape:
    try:
        shape = getattr(obj, "Shape", None)
        if shape is not None and not (hasattr(shape, "isNull") and shape.isNull()):
            shape_info = {
                "shape_type": shape.ShapeType,
                "volume": shape.Volume if hasattr(shape, "Volume") else None,
                "area": shape.Area if hasattr(shape, "Area") else None,
                "is_valid": shape.isValid(),
                "is_closed": shape.isClosed() if hasattr(shape, "isClosed") else False,
                "vertex_count": len(shape.Vertexes) if hasattr(shape, "Vertexes") else 0,
                "edge_count": len(shape.Edges) if hasattr(shape, "Edges") else 0,
                "face_count": len(shape.Faces) if hasattr(shape, "Faces") else 0,
            }
    except Exception:
        shape_info = None

_result_ = {
    "name": _xml_text(obj.Name),
    "label": _xml_text(obj.Label),
    "type_id": _xml_text(obj.TypeId),
    "properties": props,
    "shape_info": shape_info,
    "children": [_xml_text(c.Name) for c in obj.OutList] if hasattr(obj, "OutList") else [],
    "parents": [_xml_text(p.Name) for p in obj.InList] if hasattr(obj, "InList") else [],
    "visibility": obj.ViewObject.Visibility if hasattr(obj, "ViewObject") and obj.ViewObject else True,
}
"""


def build_object_inspection_code(
    obj_name: str,
    doc_name: str | None,
    *,
    include_properties: bool = True,
    include_shape: bool = True,
) -> str:
    """Build the FreeCAD-side program for inspecting one object.

    Args:
        obj_name: Internal object name.
        doc_name: Document name, or None for the active document.
        include_properties: Read and serialize object properties.
        include_shape: Read shape details.

    Returns:
        Python source to execute inside FreeCAD.
    """
    return (
        f"_obj_name = {obj_name!r}\n"
        f"_doc_name = {doc_name!r}\n"
        f"_include_properties = {include_properties!r}\n"
        f"_include_shape = {include_shape!r}\n" + _INSPECTION_PROGRAM
    )
