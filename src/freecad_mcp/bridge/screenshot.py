"""Generate the shared FreeCAD GUI screenshot operation for all bridges."""


def build_screenshot_code(
    doc_name: str | None, view_angle: str, width: int, height: int
) -> str:
    """Build a capture that restores the camera and removes its temporary file.

    Args:
        doc_name: Document to capture, or None for the active document.
        view_angle: Requested camera orientation.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        Python source to execute in FreeCAD's GUI thread.
    """
    return f"""
import base64
import os
import tempfile

requested_doc = {doc_name!r}
doc = FreeCAD.ActiveDocument if requested_doc is None else FreeCAD.getDocument(requested_doc)
if doc is None:
    raise ValueError("No document found")
if not FreeCAD.GuiUp:
    raise RuntimeError("GUI not available")
gui_doc = FreeCADGui.getDocument(doc.Name)
if gui_doc is None:
    raise ValueError("Document has no GUI view")
view = gui_doc.activeView()
if view is None:
    raise ValueError("No active view")
required = ("saveImage", "getCamera", "setCamera", "fitAll")
if not all(callable(getattr(view, name, None)) for name in required):
    raise ValueError("Cannot capture screenshot: active view is not a supported 3D view")
angle = {view_angle!r}
method = {{"Isometric": "viewIsometric", "Front": "viewFront", "Back": "viewRear", "Top": "viewTop", "Bottom": "viewBottom", "Left": "viewLeft", "Right": "viewRight"}}.get(angle)
if method is not None and not callable(getattr(view, method, None)):
    raise ValueError("Cannot capture screenshot: active view does not support the requested angle")

# Save before any orientation or framing changes, including on failed captures.
animation_getter = getattr(view, "isAnimationEnabled", None)
animation_setter = getattr(view, "setAnimationEnabled", None)
animation = animation_getter() if callable(animation_getter) and callable(animation_setter) else None
temp_path = None
camera = None
try:
    if animation is not None:
        animation_setter(False)
    camera = view.getCamera()
    if method is not None:
        getattr(view, method)()
    FreeCADGui.updateGui()
    view.fitAll()
    FreeCADGui.updateGui()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
        temp_path = image_file.name
    view.saveImage(temp_path, {width}, {height}, "Current")
    with open(temp_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("ascii")
finally:
    try:
        if camera is not None:
            view.setCamera(camera)
            FreeCADGui.updateGui()
    finally:
        try:
            if temp_path is not None:
                os.unlink(temp_path)
        finally:
            if animation is not None:
                animation_setter(animation)

_result_ = {{"success": True, "data": image_data, "format": "png", "width": {width}, "height": {height}}}
"""
