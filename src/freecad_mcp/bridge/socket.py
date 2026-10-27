"""Socket bridge for FreeCAD communication via JSON-RPC.

This bridge communicates with FreeCAD using JSON-RPC over TCP sockets,
providing a modern, lightweight alternative to XML-RPC.

Based on learnings from competitive analysis:
- Simple socket-based approach (inspired by bonninr/freecad_mcp)
- Connection recovery mechanisms (from jango-blockchained)
- Automatic reconnection on connection loss
"""

import asyncio
import contextlib
import json
import time
import uuid
from typing import Any

from freecad_mcp.bridge.base import (
    DEFAULT_EXECUTION_TIMEOUT_MS,
    ConnectionStatus,
    DocumentInfo,
    ExecutionResult,
    FreecadBridge,
    MacroInfo,
    ObjectInfo,
    ScreenshotResult,
    ViewAngle,
    WorkbenchInfo,
    resolve_execution_timeout_ms,
)
from freecad_mcp.bridge.object_inspection import build_object_inspection_code

DEFAULT_SOCKET_HOST = "localhost"
DEFAULT_SOCKET_PORT = 9876
DEFAULT_TIMEOUT = 30.0
EXECUTION_RESPONSE_GRACE_SECONDS = 1.0


class JsonRpcError(Exception):
    """JSON-RPC error response."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        """Initialize JSON-RPC error.

        Args:
            code: Error code.
            message: Error message.
            data: Additional error data.
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


class RequestNotSentError(TimeoutError):
    """Request deadline expired before any write attempt to FreeCAD."""


class SocketBridge(FreecadBridge):
    """Bridge that communicates with FreeCAD via JSON-RPC over sockets.

    This bridge provides a lightweight, modern protocol for FreeCAD
    communication. It supports automatic reconnection and connection
    health monitoring.

    Attributes:
        host: Socket server hostname.
        port: Socket server port.
        timeout: Connection and request timeout in seconds.
    """

    def __init__(
        self,
        host: str = DEFAULT_SOCKET_HOST,
        port: int = DEFAULT_SOCKET_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        auto_reconnect: bool = True,
        *,
        execution_timeout_ms: int = DEFAULT_EXECUTION_TIMEOUT_MS,
    ) -> None:
        """Initialize the socket bridge.

        Args:
            host: Socket server hostname.
            port: Socket server port.
            timeout: Connection and request timeout in seconds.
            auto_reconnect: Whether to automatically reconnect on connection loss.
            execution_timeout_ms: Default execution timeout in milliseconds.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._execution_timeout_ms = resolve_execution_timeout_ms(
            execution_timeout_ms,
            DEFAULT_EXECUTION_TIMEOUT_MS,
        )
        self._auto_reconnect = auto_reconnect
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._lock = asyncio.Lock()
        self._reconnect_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish connection to FreeCAD socket server.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        try:
            await self._open_streams()
            await self.ping()
        except TimeoutError as e:
            await self.disconnect()
            msg = f"Connection to {self._host}:{self._port} timed out"
            raise ConnectionError(msg) from e
        except Exception as e:
            await self.disconnect()
            msg = f"Failed to connect to {self._host}:{self._port}: {e}"
            raise ConnectionError(msg) from e

    async def _open_streams(self) -> None:
        """Open socket streams without issuing a nested request."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=self._timeout,
        )
        self._connected = True

    async def disconnect(self) -> None:
        """Close connection to FreeCAD socket server."""
        writer = self._writer
        self._reader = None
        self._writer = None
        self._connected = False
        if writer:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def is_connected(self) -> bool:
        """Check if bridge is connected to FreeCAD."""
        if not self._connected or self._writer is None:
            return False

        try:
            await self.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def _get_request_streams(
        self,
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Return the current request streams.

        Returns:
            The active reader and writer streams.

        Raises:
            ConnectionError: If the bridge is not currently connected.
        """
        if self._connected and self._writer is not None and self._reader is not None:
            if self._reader.at_eof() is True or self._writer.is_closing() is True:
                self._discard_request_streams(self._writer)
                raise ConnectionError("Socket connection has closed")
            return self._reader, self._writer

        msg = "Not connected to socket server"
        raise ConnectionError(msg)

    async def _reconnect_request_streams(self) -> None:
        """Replace missing request streams without holding the request lock.

        Raises:
            ConnectionError: If replacement streams cannot be established.
        """
        async with self._reconnect_lock:
            if (
                self._connected
                and self._writer is not None
                and self._reader is not None
            ):
                return

            await self.disconnect()
            try:
                await self._open_streams()
            except Exception as e:
                await self.disconnect()
                msg = "Not connected to socket server"
                raise ConnectionError(msg) from e

    async def _reconnect_before_deadline(self, deadline: float) -> None:
        """Reconnect while the caller's pre-send deadline remains.

        Args:
            deadline: Absolute event-loop time by which the request must be sent.

        Raises:
            TimeoutError: If the deadline expires during reconnection.
            ConnectionError: If reconnection fails.
        """
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError

        await asyncio.wait_for(
            self._reconnect_request_streams(),
            timeout=remaining,
        )

    async def _send_request_once(
        self,
        request: dict[str, Any],
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        response_timeout: float,
    ) -> Any:
        """Send one request over streams selected under the request lock.

        Args:
            request: JSON-RPC request payload.
            reader: Current response stream.
            writer: Current request stream.
            response_timeout: Response timeout in seconds.

        Returns:
            Result from the JSON-RPC response.

        Raises:
            ConnectionError: If the server closes the connection or returns
                invalid JSON.
            JsonRpcError: If the server returns an error response.
            TimeoutError: If the response deadline expires.
        """
        try:
            request_data = json.dumps(request).encode("utf-8") + b"\n"
            async with asyncio.timeout(response_timeout):
                writer.write(request_data)
                await writer.drain()
                response_data = await reader.readline()
        except TimeoutError:
            self._discard_request_streams(writer)
            raise

        if not response_data:
            self._connected = False
            msg = "Connection closed by server"
            raise ConnectionError(msg)

        try:
            response = json.loads(response_data.decode("utf-8"))
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON response: {e}"
            raise ConnectionError(msg) from e

        if "error" in response:
            error = response["error"]
            raise JsonRpcError(
                code=error.get("code", -1),
                message=error.get("message", "Unknown error"),
                data=error.get("data"),
            )

        return response.get("result")

    def _discard_request_streams(self, writer: asyncio.StreamWriter) -> None:
        """Close and clear a failed stream pair.

        Args:
            writer: Writer associated with the failed request.
        """
        writer.close()
        if self._writer is writer:
            self._reader = None
            self._writer = None
            self._connected = False

    async def _acquire_request_lock(self, deadline: float) -> None:
        """Acquire the request lock before an absolute send deadline.

        Args:
            deadline: Absolute event-loop time by which the lock must be acquired.

        Raises:
            TimeoutError: If the deadline expires while waiting for the lock.
        """
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError
        await asyncio.wait_for(self._lock.acquire(), timeout=remaining)

    @staticmethod
    def _connection_failure_message(
        error: ConnectionError | ConnectionResetError | BrokenPipeError,
    ) -> str:
        """Return the public message for a recoverable connection failure."""
        if isinstance(error, (ConnectionResetError, BrokenPipeError)):
            return f"Connection lost: {error}"
        return "Not connected to socket server"

    async def _recover_request_connection(
        self,
        error: ConnectionError | ConnectionResetError | BrokenPipeError,
        deadline: float,
    ) -> None:
        """Recover a request connection outside the request lock.

        Args:
            error: Failure that required reconnection.
            deadline: Absolute event-loop time by which the request must be sent.

        Raises:
            ConnectionError: If reconnection is disabled or fails.
            TimeoutError: If the request deadline expires during reconnection.
        """
        message = self._connection_failure_message(error)
        if not self._auto_reconnect:
            raise ConnectionError(message) from error

        try:
            await self._reconnect_before_deadline(deadline)
        except ConnectionError as e:
            raise ConnectionError(message) from e

    @staticmethod
    def _request_deadline_error(request_may_have_been_sent: bool) -> TimeoutError:
        """Classify a pre-send deadline based on earlier write attempts.

        Args:
            request_may_have_been_sent: Whether this logical request has already
                reached a stream write attempt.

        Returns:
            A conservative timeout when an earlier attempt may have reached
            FreeCAD, otherwise a definitive request-not-sent timeout.
        """
        if request_may_have_been_sent:
            return TimeoutError()
        return RequestNotSentError()

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        response_timeout: float | None = None,
        request_timeout: float | None = None,
    ) -> Any:
        """Send a JSON-RPC request and wait for response.

        Args:
            method: Method name to call.
            params: Method parameters.
            response_timeout: Optional response timeout in seconds. The bridge
                connection timeout applies when omitted.
            request_timeout: Optional deadline in seconds for acquiring the
                request lock and sending the request. The bridge connection
                timeout applies when omitted.

        Returns:
            Result from the JSON-RPC response.

        Raises:
            ConnectionError: If not connected.
            JsonRpcError: If server returns an error.
            TimeoutError: If the request or response deadline expires.
        """
        request_id = str(uuid.uuid4())
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {},
        }
        response_deadline = (
            self._timeout if response_timeout is None else response_timeout
        )
        send_deadline = asyncio.get_running_loop().time() + (
            self._timeout if request_timeout is None else request_timeout
        )
        request_may_have_been_sent = False

        while True:
            try:
                await self._acquire_request_lock(send_deadline)
            except TimeoutError as e:
                raise self._request_deadline_error(request_may_have_been_sent) from e

            recovery_error: ConnectionError | ConnectionResetError | BrokenPipeError
            try:
                if asyncio.get_running_loop().time() >= send_deadline:
                    raise self._request_deadline_error(request_may_have_been_sent)

                try:
                    reader, writer = self._get_request_streams()
                except ConnectionError as e:
                    recovery_error = e
                else:
                    request_may_have_been_sent = True
                    try:
                        return await self._send_request_once(
                            request,
                            reader,
                            writer,
                            response_deadline,
                        )
                    except (ConnectionResetError, BrokenPipeError) as e:
                        self._discard_request_streams(writer)
                        recovery_error = e
            finally:
                self._lock.release()

            try:
                await self._recover_request_connection(recovery_error, send_deadline)
            except TimeoutError as e:
                raise self._request_deadline_error(request_may_have_been_sent) from e

    async def ping(self) -> float:
        """Ping FreeCAD to check connection and measure latency.

        Returns:
            Round-trip time in milliseconds.

        Raises:
            ConnectionError: If not connected.
        """
        start = time.perf_counter()
        await self._send_request("ping")
        return (time.perf_counter() - start) * 1000

    async def get_status(self) -> ConnectionStatus:
        """Get detailed connection status.

        Returns:
            ConnectionStatus with full status information.
        """
        if not self._connected:
            return ConnectionStatus(
                connected=False,
                mode="socket",
                error="Not connected",
            )

        try:
            ping_ms = await self.ping()
            version_info = await self.get_freecad_version()
            gui_available = await self.is_gui_available()

            return ConnectionStatus(
                connected=True,
                mode="socket",
                freecad_version=version_info.get("version", "unknown"),
                gui_available=gui_available,
                last_ping_ms=ping_ms,
            )
        except Exception as e:
            return ConnectionStatus(
                connected=False,
                mode="socket",
                error=str(e),
            )

    # =========================================================================
    # Code Execution
    # =========================================================================

    async def execute_python(
        self,
        code: str,
        timeout_ms: int | None = None,
    ) -> ExecutionResult:
        """Execute Python code in FreeCAD context via socket.

        Args:
            code: Python code to execute.
            timeout_ms: Optional per-call timeout in milliseconds. The configured
                bridge default applies when omitted.

        Returns:
            ExecutionResult with execution outcome.
        """
        try:
            effective_timeout_ms = resolve_execution_timeout_ms(
                timeout_ms,
                self._execution_timeout_ms,
            )
        except ValueError as e:
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                error_type="ValueError",
            )

        start = time.perf_counter()

        try:
            result = await self._send_request(
                "execute",
                {"code": code, "timeout_ms": effective_timeout_ms},
                response_timeout=(
                    effective_timeout_ms / 1000 + EXECUTION_RESPONSE_GRACE_SECONDS
                ),
                request_timeout=effective_timeout_ms / 1000,
            )
            elapsed = (time.perf_counter() - start) * 1000

            if isinstance(result, dict):
                return ExecutionResult(
                    success=result.get("success", False),
                    result=result.get("result"),
                    stdout=result.get("stdout", ""),
                    stderr=(result.get("stderr") or result.get("error_message", "")),
                    execution_time_ms=elapsed,
                    error_type=result.get("error_type"),
                    error_traceback=result.get("error_traceback"),
                )
            else:
                return ExecutionResult(
                    success=True,
                    result=result,
                    stdout="",
                    stderr="",
                    execution_time_ms=elapsed,
                )

        except TimeoutError as e:
            if isinstance(e, RequestNotSentError):
                error_message = (
                    f"Execution request expired after {effective_timeout_ms}ms "
                    "before being sent; code was not executed"
                )
                error_type = "RequestNotSentError"
            else:
                error_message = (
                    f"Execution response timed out after {effective_timeout_ms}ms; "
                    "code already running in FreeCAD may continue"
                )
                error_type = "TimeoutError"
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr=error_message,
                execution_time_ms=float(effective_timeout_ms),
                error_type=error_type,
            )
        except JsonRpcError as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr=e.message,
                execution_time_ms=elapsed,
                error_type="JsonRpcError",
            )
        except ConnectionError as e:
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr=str(e),
                execution_time_ms=0,
                error_type="ConnectionError",
            )

    # =========================================================================
    # Document Management
    # =========================================================================

    async def get_documents(self) -> list[DocumentInfo]:
        """Get list of open documents."""
        result = await self.execute_python(
            """
_result_ = []
for doc in FreeCAD.listDocuments().values():
    _result_.append({
        "name": doc.Name,
        "label": doc.Label,
        "path": doc.FileName or None,
        "objects": [obj.Name for obj in doc.Objects],
        "is_modified": doc.Modified if hasattr(doc, "Modified") else False,
        "active_object": doc.ActiveObject.Name if doc.ActiveObject else None,
    })
"""
        )

        if result.success and result.result:
            return [DocumentInfo(**doc) for doc in result.result]
        return []

    async def get_active_document(self) -> DocumentInfo | None:
        """Get the active document."""
        result = await self.execute_python(
            """
doc = FreeCAD.ActiveDocument
if doc:
    _result_ = {
        "name": doc.Name,
        "label": doc.Label,
        "path": doc.FileName or None,
        "objects": [obj.Name for obj in doc.Objects],
        "is_modified": doc.Modified if hasattr(doc, "Modified") else False,
        "active_object": doc.ActiveObject.Name if doc.ActiveObject else None,
    }
else:
    _result_ = None
"""
        )

        if result.success and result.result:
            return DocumentInfo(**result.result)
        return None

    async def create_document(
        self, name: str, label: str | None = None
    ) -> DocumentInfo:
        """Create a new document."""
        label = label or name
        result = await self.execute_python(
            f"""
doc = FreeCAD.newDocument({name!r})
doc.Label = {label!r}
_result_ = {{
    "name": doc.Name,
    "label": doc.Label,
    "path": doc.FileName or None,
    "objects": [],
    "is_modified": False,
}}
"""
        )

        if result.success and result.result:
            return DocumentInfo(**result.result)

        error_msg = result.error_traceback or "Failed to create document"
        raise ValueError(error_msg)

    async def open_document(self, path: str) -> DocumentInfo:
        """Open an existing document."""
        result = await self.execute_python(
            f"""
import os
if not os.path.exists({path!r}):
    raise FileNotFoundError(f"File not found: {path!r}")

doc = FreeCAD.openDocument({path!r})
_result_ = {{
    "name": doc.Name,
    "label": doc.Label,
    "path": doc.FileName or None,
    "objects": [obj.Name for obj in doc.Objects],
    "is_modified": doc.Modified if hasattr(doc, "Modified") else False,
}}
"""
        )

        if result.success and result.result:
            return DocumentInfo(**result.result)

        if "FileNotFoundError" in (result.error_type or ""):
            raise FileNotFoundError(result.stderr)

        error_msg = result.error_traceback or "Failed to open document"
        raise ValueError(error_msg)

    async def save_document(
        self,
        doc_name: str | None = None,
        path: str | None = None,
    ) -> str:
        """Save a document."""
        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No active document" if {doc_name!r} is None else f"Document not found: {doc_name!r}")

save_path = {path!r} or doc.FileName
if not save_path:
    raise ValueError("No path specified for new document")

doc.saveAs(save_path)
_result_ = save_path
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return result.result

        error_msg = result.error_traceback or "Failed to save document"
        raise ValueError(error_msg)

    async def close_document(self, doc_name: str | None = None) -> None:
        """Close a document."""
        code = f"""
doc_name = {doc_name!r}
if doc_name is None:
    doc = FreeCAD.ActiveDocument
    if doc:
        doc_name = doc.Name
    else:
        raise ValueError("No active document")

FreeCAD.closeDocument(doc_name)
_result_ = True
"""
        result = await self.execute_python(code)

        if not result.success:
            error_msg = result.error_traceback or "Failed to close document"
            raise ValueError(error_msg)

    # =========================================================================
    # Object Management
    # =========================================================================

    async def get_objects(self, doc_name: str | None = None) -> list[ObjectInfo]:
        """Get all objects in a document."""
        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

objects = []
for obj in doc.Objects:
    obj_info = {{
        "name": obj.Name,
        "label": obj.Label,
        "type_id": obj.TypeId,
        "visibility": obj.ViewObject.Visibility if hasattr(obj, "ViewObject") and obj.ViewObject else True,
        "children": [c.Name for c in obj.OutList] if hasattr(obj, "OutList") else [],
        "parents": [p.Name for p in obj.InList] if hasattr(obj, "InList") else [],
    }}
    objects.append(obj_info)

_result_ = objects
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return [ObjectInfo(**obj) for obj in result.result]
        return []

    async def get_object(
        self,
        obj_name: str,
        doc_name: str | None = None,
        *,
        include_properties: bool = True,
        include_shape: bool = True,
    ) -> ObjectInfo:
        """Get detailed object information."""
        code = build_object_inspection_code(
            obj_name,
            doc_name,
            include_properties=include_properties,
            include_shape=include_shape,
        )
        result = await self.execute_python(code)

        if result.success and result.result:
            return ObjectInfo(**result.result)

        error_msg = result.error_traceback or result.stderr or "Failed to get object"
        raise ValueError(error_msg)

    async def create_object(
        self,
        type_id: str,
        name: str | None = None,
        properties: dict[str, Any] | None = None,
        doc_name: str | None = None,
    ) -> ObjectInfo:
        """Create a new object."""
        properties = properties or {}
        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.addObject({type_id!r}, {name!r} or "")

# Set properties
for prop_name, prop_val in {properties!r}.items():
    if hasattr(obj, prop_name):
        setattr(obj, prop_name, prop_val)

doc.recompute()

_result_ = {{
    "name": obj.Name,
    "label": obj.Label,
    "type_id": obj.TypeId,
    "visibility": True,
    "children": [c.Name for c in obj.OutList] if hasattr(obj, "OutList") else [],
    "parents": [p.Name for p in obj.InList] if hasattr(obj, "InList") else [],
}}
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return ObjectInfo(**result.result)

        error_msg = result.error_traceback or "Failed to create object"
        raise ValueError(error_msg)

    async def edit_object(
        self,
        obj_name: str,
        properties: dict[str, Any],
        doc_name: str | None = None,
    ) -> ObjectInfo:
        """Edit object properties."""
        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({obj_name!r})
if obj is None:
    raise ValueError(f"Object not found: {obj_name!r}")

# Set properties
for prop_name, prop_val in {properties!r}.items():
    if hasattr(obj, prop_name):
        setattr(obj, prop_name, prop_val)

doc.recompute()

_result_ = {{
    "name": obj.Name,
    "label": obj.Label,
    "type_id": obj.TypeId,
    "visibility": obj.ViewObject.Visibility if hasattr(obj, "ViewObject") and obj.ViewObject else True,
    "children": [c.Name for c in obj.OutList] if hasattr(obj, "OutList") else [],
    "parents": [p.Name for p in obj.InList] if hasattr(obj, "InList") else [],
}}
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return ObjectInfo(**result.result)

        error_msg = result.error_traceback or "Failed to edit object"
        raise ValueError(error_msg)

    async def delete_object(
        self,
        obj_name: str,
        doc_name: str | None = None,
    ) -> None:
        """Delete an object."""
        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

obj = doc.getObject({obj_name!r})
if obj is None:
    raise ValueError(f"Object not found: {obj_name!r}")

doc.removeObject({obj_name!r})
_result_ = True
"""
        result = await self.execute_python(code)

        if not result.success:
            error_msg = result.error_traceback or "Failed to delete object"
            raise ValueError(error_msg)

    # =========================================================================
    # View and Screenshot
    # =========================================================================

    async def get_screenshot(
        self,
        view_angle: ViewAngle | None = None,
        width: int = 800,
        height: int = 600,
        doc_name: str | None = None,
    ) -> ScreenshotResult:
        """Capture a screenshot of the 3D view via socket."""
        view_angle_str = view_angle.value if view_angle else "Isometric"
        code = f"""
import base64
import tempfile
import os

doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

# Check if GUI is available
if not FreeCAD.GuiUp:
    raise RuntimeError("GUI not available")

view = FreeCADGui.ActiveDocument.ActiveView
if view is None:
    raise ValueError("No active view")

# Check view type
view_type = view.__class__.__name__
if view_type not in ["View3DInventor", "View3DInventorPy"]:
    raise ValueError(f"Cannot capture screenshot from {{view_type}} view")

# Set view angle
view_type_str = {view_angle_str!r}
if view_type_str == "FitAll":
    view.fitAll()
elif view_type_str == "Isometric":
    view.viewIsometric()
elif view_type_str == "Front":
    view.viewFront()
elif view_type_str == "Back":
    view.viewRear()
elif view_type_str == "Top":
    view.viewTop()
elif view_type_str == "Bottom":
    view.viewBottom()
elif view_type_str == "Left":
    view.viewLeft()
elif view_type_str == "Right":
    view.viewRight()

# Save to temp file and read
with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
    temp_path = f.name

view.saveImage(temp_path, {width}, {height}, "Current")

with open(temp_path, "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")

os.unlink(temp_path)

_result_ = {{
    "success": True,
    "data": image_data,
    "format": "png",
    "width": {width},
    "height": {height},
}}
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return ScreenshotResult(
                success=True,
                data=result.result["data"],
                format=result.result["format"],
                width=result.result["width"],
                height=result.result["height"],
                view_angle=view_angle,
            )

        return ScreenshotResult(
            success=False,
            error=result.error_traceback
            or result.stderr
            or "Failed to capture screenshot",
            width=width,
            height=height,
            view_angle=view_angle,
        )

    async def set_view(
        self,
        view_angle: ViewAngle,
        doc_name: str | None = None,
    ) -> None:
        """Set the 3D view angle."""
        view_angle_str = view_angle.value
        code = f"""
doc = FreeCAD.ActiveDocument if {doc_name!r} is None else FreeCAD.getDocument({doc_name!r})
if doc is None:
    raise ValueError("No document found")

if not FreeCAD.GuiUp:
    _result_ = True
else:
    view = FreeCADGui.ActiveDocument.ActiveView
    if view is None:
        raise ValueError("No active view")

    view_type = {view_angle_str!r}
    if view_type == "FitAll":
        view.fitAll()
    elif view_type == "Isometric":
        view.viewIsometric()
    elif view_type == "Front":
        view.viewFront()
    elif view_type == "Back":
        view.viewRear()
    elif view_type == "Top":
        view.viewTop()
    elif view_type == "Bottom":
        view.viewBottom()
    elif view_type == "Left":
        view.viewLeft()
    elif view_type == "Right":
        view.viewRight()

    _result_ = True
"""
        await self.execute_python(code)

    # =========================================================================
    # Macros
    # =========================================================================

    async def get_macros(self) -> list[MacroInfo]:
        """Get list of available macros."""
        code = """
import os

macro_paths = []

user_path = FreeCAD.getUserMacroDir(True)
if os.path.exists(user_path):
    macro_paths.append(("user", user_path))

system_path = FreeCAD.getResourceDir() + "Macro"
if os.path.exists(system_path):
    macro_paths.append(("system", system_path))

macros = []
for source, path in macro_paths:
    for filename in os.listdir(path):
        if filename.endswith(".FCMacro"):
            macro_file = os.path.join(path, filename)
            description = ""
            try:
                with open(macro_file, "r") as f:
                    for line in f:
                        if line.startswith("#"):
                            desc = line.lstrip("#").strip()
                            if desc and not desc.startswith("!") and not desc.startswith("-*-"):
                                description = desc
                                break
            except Exception:
                pass

            macros.append({
                "name": filename[:-8],
                "path": macro_file,
                "description": description,
                "is_system": source == "system",
            })

_result_ = macros
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return [MacroInfo(**m) for m in result.result]
        return []

    async def run_macro(
        self,
        macro_name: str,
        args: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Run a macro by name."""
        args = args or {}
        code = f"""
import os

macro_name = {macro_name!r}
macro_file = None

user_path = FreeCAD.getUserMacroDir(True)
user_macro = os.path.join(user_path, macro_name + ".FCMacro")
if os.path.exists(user_macro):
    macro_file = user_macro

if not macro_file:
    system_path = FreeCAD.getResourceDir() + "Macro"
    system_macro = os.path.join(system_path, macro_name + ".FCMacro")
    if os.path.exists(system_macro):
        macro_file = system_macro

if not macro_file:
    raise FileNotFoundError(f"Macro not found: {{macro_name}}")

args = {args!r}
for k, v in args.items():
    exec(f"{{k}} = {{v!r}}")

with open(macro_file, "r") as f:
    macro_code = f.read()

exec(macro_code)
_result_ = True
"""
        return await self.execute_python(code)

    async def create_macro(
        self,
        name: str,
        code: str,
        description: str = "",
    ) -> MacroInfo:
        """Create a new macro."""
        create_code = f"""
import os

macro_path = FreeCAD.getUserMacroDir(True)
os.makedirs(macro_path, exist_ok=True)

macro_file = os.path.join(macro_path, {name!r} + ".FCMacro")

header = ""
if {description!r}:
    header = f"# {description!r}\\n\\n"

full_code = header + '''# -*- coding: utf-8 -*-
# FreeCAD Macro: {name}
# Created via MCP Bridge

import FreeCAD
import FreeCADGui

''' + {code!r}

with open(macro_file, "w") as f:
    f.write(full_code)

_result_ = {{
    "name": {name!r},
    "path": macro_file,
    "description": {description!r},
    "is_system": False,
}}
"""
        result = await self.execute_python(create_code)

        if result.success and result.result:
            return MacroInfo(**result.result)

        error_msg = result.error_traceback or "Failed to create macro"
        raise ValueError(error_msg)

    # =========================================================================
    # Workbenches
    # =========================================================================

    async def get_workbenches(self) -> list[WorkbenchInfo]:
        """Get list of available workbenches."""
        code = """
workbenches = []
active_wb = FreeCADGui.activeWorkbench() if FreeCAD.GuiUp else None
active_name = active_wb.__class__.__name__ if active_wb else None

if FreeCAD.GuiUp:
    for name in FreeCADGui.listWorkbenches():
        wb = FreeCADGui.getWorkbench(name)
        workbenches.append({
            "name": name,
            "label": wb.MenuText if hasattr(wb, "MenuText") else name,
            "icon": wb.Icon if hasattr(wb, "Icon") else "",
            "is_active": name == active_name,
        })
else:
    common = ["StartWorkbench", "PartWorkbench", "PartDesignWorkbench",
              "DraftWorkbench", "SketcherWorkbench", "MeshWorkbench"]
    for name in common:
        workbenches.append({
            "name": name,
            "label": name.replace("Workbench", ""),
            "icon": "",
            "is_active": False,
        })

_result_ = workbenches
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return [WorkbenchInfo(**wb) for wb in result.result]
        return []

    async def activate_workbench(self, workbench_name: str) -> None:
        """Activate a workbench."""
        code = f"""
if FreeCAD.GuiUp:
    try:
        FreeCADGui.activateWorkbench({workbench_name!r})
        _result_ = True
    except Exception as e:
        raise ValueError(f"Failed to activate workbench: {{e}}")
else:
    _result_ = True
"""
        result = await self.execute_python(code)

        if not result.success:
            error_msg = result.error_traceback or "Failed to activate workbench"
            raise ValueError(error_msg)

    # =========================================================================
    # Version and Environment
    # =========================================================================

    async def get_freecad_version(self) -> dict[str, Any]:
        """Get FreeCAD version information."""
        code = """
import sys
_result_ = {
    "version": ".".join(str(x) for x in FreeCAD.Version()[:3]),
    "version_tuple": FreeCAD.Version()[:3],
    "build_date": FreeCAD.Version()[3] if len(FreeCAD.Version()) > 3 else "unknown",
    "python_version": sys.version,
    "gui_available": FreeCAD.GuiUp,
}
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return result.result

        return {
            "version": "unknown",
            "version_tuple": [],
            "build_date": "unknown",
            "python_version": "",
            "gui_available": False,
        }

    async def is_gui_available(self) -> bool:
        """Check if FreeCAD GUI is available."""
        result = await self.execute_python("_result_ = FreeCAD.GuiUp")
        return bool(result.success and result.result)

    # =========================================================================
    # Console
    # =========================================================================

    async def get_console_output(self, lines: int = 100) -> list[str]:
        """Get recent console output."""
        code = f"""
output_lines = []

if hasattr(FreeCAD, 'Console'):
    console = FreeCAD.Console
    if hasattr(console, 'GetLog'):
        log = console.GetLog()
        if log:
            output_lines = log.split('\\n')[-{lines}:]

_result_ = output_lines
"""
        result = await self.execute_python(code)

        if result.success and result.result:
            return result.result
        return []
