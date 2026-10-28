"""XML-RPC bridge for FreeCAD GUI mode communication.

This bridge connects to a FreeCAD instance running an XML-RPC server,
allowing remote control while FreeCAD has its GUI open.

Compatible with neka-nat/freecad-mcp XML-RPC protocol, providing
interoperability with existing FreeCAD Robust MCP addons.

Design inspired by neka-nat/freecad-mcp (MIT License):
- Uses neka-nat's proven XML-RPC protocol (port 9875)
- Connection health monitoring and auto-reconnect
- Timeout handling for long operations

Attribution:
    The XML-RPC protocol design and port selection (9875) were inspired by
    neka-nat/freecad-mcp (https://github.com/neka-nat/freecad-mcp), which is
    licensed under the MIT License. This implementation is a complete rewrite
    that maintains protocol compatibility.
"""

import asyncio
import base64
import http.client
import time
import xmlrpc.client
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from freecad_mcp.bridge.authentication import request_proof_message
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
from freecad_mcp.bridge.screenshot import build_screenshot_code

DEFAULT_XMLRPC_HOST = "localhost"
DEFAULT_XMLRPC_PORT = 9875
DEFAULT_TIMEOUT = 30.0
EXECUTION_RESPONSE_GRACE_SECONDS = 1.0
LEGACY_EXECUTE_ARITY_FAULT = (
    "<class 'TypeError'>:FreecadMCPPlugin._xmlrpc_execute() takes 2 "
    "positional arguments but 3 were given"
)


class AuthenticatedXmlRpcTransport(xmlrpc.client.Transport):
    """Authenticate exact XML request bytes without automatic request retries."""

    def __init__(
        self, client_id: str, signer: Callable[[bytes], bytes], timeout: float
    ) -> None:
        """Initialize a transport with a paired identity and protected signer."""
        super().__init__()
        self._client_id = client_id
        self._signer = signer
        self._timeout = timeout

    def request(
        self,
        host: str | tuple[str, dict[str, str]],
        handler: str,
        request_body: Any,
        verbose: bool = False,
    ) -> Any:
        """Issue one challenge and send exactly one authenticated XML request."""
        if isinstance(host, tuple):
            host = host[0]
        request_body = bytes(request_body)
        connection = http.client.HTTPConnection(host, timeout=self._timeout)
        self.verbose = verbose
        try:
            connection.request("GET", "/challenge")
            response = connection.getresponse()
            if response.status != 200:
                raise ConnectionError("Bridge did not provide a challenge")
            challenge_bytes = response.read(128)
            if len(challenge_bytes) != 43:
                raise ConnectionError("Bridge provided an invalid challenge")
            try:
                challenge = challenge_bytes.decode("ascii")
                message = request_proof_message(
                    self._client_id, challenge, "xmlrpc", request_body
                )
            except (UnicodeDecodeError, ValueError) as e:
                raise ConnectionError("Bridge provided an invalid challenge") from e
            try:
                proof = self._signer(message)
            except Exception as e:
                raise ConnectionError("Bridge signer is unavailable") from e
            if not isinstance(proof, bytes) or not proof or len(proof) > 8192:
                raise ConnectionError("Bridge signer returned an invalid proof")
            headers = {
                "Content-Type": "text/xml",
                "X-FreeCAD-Client": self._client_id,
                "X-FreeCAD-Challenge": challenge,
                "X-FreeCAD-Proof": base64.b64encode(proof).decode("ascii"),
            }
            connection.request("POST", handler, body=request_body, headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                raise xmlrpc.client.ProtocolError(
                    host + handler,
                    response.status,
                    response.reason,
                    dict(response.getheaders()),
                )
            return self.parse_response(response)
        finally:
            connection.close()


def _is_legacy_execute_arity_fault(error: xmlrpc.client.Fault) -> bool:
    """Return whether a fault identifies the previous one-argument handler.

    The exact dispatcher fault from this project's previous workbench release is
    matched so an unrelated ``TypeError`` from a different XML-RPC server cannot
    cause state-changing Python code to be retried.

    Args:
        error: XML-RPC fault raised by the remote server.

    Returns:
        True only for the prior ``FreecadMCPPlugin._xmlrpc_execute`` signature.
    """
    return error.faultCode == 1 and error.faultString == LEGACY_EXECUTE_ARITY_FAULT


class XmlRpcBridge(FreecadBridge):
    """Bridge that communicates with FreeCAD via XML-RPC.

    This bridge connects to a FreeCAD instance that is running the
    XML-RPC server addon. It provides full access to FreeCAD functionality
    including GUI operations like screenshots.

    Attributes:
        host: XML-RPC server hostname.
        port: XML-RPC server port.
        timeout: Connection and request timeout in seconds.
    """

    def __init__(
        self,
        host: str = DEFAULT_XMLRPC_HOST,
        port: int = DEFAULT_XMLRPC_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        execution_timeout_ms: int = DEFAULT_EXECUTION_TIMEOUT_MS,
        *,
        client_id: str | None = None,
        signer: Callable[[bytes], bytes] | None = None,
    ) -> None:
        """Initialize the XML-RPC bridge.

        Args:
            host: XML-RPC server hostname.
            port: XML-RPC server port.
            timeout: Connection and request timeout in seconds.
            execution_timeout_ms: Default execution timeout in milliseconds.
            client_id: Identity of the paired client.
            signer: Protected provider that signs request proof messages.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._client_id = client_id
        self._signer = signer
        self._execution_timeout_ms = resolve_execution_timeout_ms(
            execution_timeout_ms,
            DEFAULT_EXECUTION_TIMEOUT_MS,
        )
        self._proxy: xmlrpc.client.ServerProxy | None = None
        self._transport: AuthenticatedXmlRpcTransport | None = None
        self._executor: ThreadPoolExecutor | None = None
        self._connected = False

    @property
    def _server_url(self) -> str:
        """Get the XML-RPC server URL."""
        host = self._host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"http://{host}:{self._port}"

    async def connect(self) -> None:
        """Establish connection to FreeCAD XML-RPC server.

        Raises:
            ConnectionError: If connection cannot be established.
        """
        try:
            if self._client_id is None or self._signer is None:
                raise ConnectionError(
                    "A paired client and protected signer are required"
                )
            self._executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="freecad-xmlrpc",
            )
            self._transport = AuthenticatedXmlRpcTransport(
                self._client_id, self._signer, self._timeout
            )
            self._proxy = xmlrpc.client.ServerProxy(
                self._server_url,
                allow_none=True,
                transport=self._transport,
            )
            # Test connection with a ping
            await self.ping()
            self._connected = True
        except ConnectionRefusedError as e:
            self._connected = False
            self._shutdown_executor()
            msg = self._get_connection_refused_message()
            raise ConnectionError(msg) from e
        except Exception as e:
            self._connected = False
            self._shutdown_executor()
            error_str = str(e)
            if "Connection refused" in error_str or "Errno 61" in error_str:
                msg = self._get_connection_refused_message()
            else:
                msg = f"Failed to connect to XML-RPC server at {self._server_url}: {e}"
            raise ConnectionError(msg) from e

    def _get_connection_refused_message(self) -> str:
        """Get a helpful error message when connection is refused."""
        return f"""
================================================================================
CONNECTION REFUSED: Cannot connect to FreeCAD at {self._server_url}

The FreeCAD Robust MCP Bridge server is not running. To fix this:

1. Start FreeCAD (the GUI application)

2. Start the MCP bridge using one of these methods:

   Option A: Using the Robust MCP Bridge Workbench (recommended)
   - Install via FreeCAD Addon Manager: Tools → Addon Manager
   - Search for "Robust MCP Bridge" and install
   - Switch to the Robust MCP Bridge workbench
   - Click "Start MCP Bridge" in the toolbar

   Option B: From source (for developers)
   - Run: just freecad::run-gui

3. You should see: "MCP Bridge started!"
   - XML-RPC: localhost:{self._port}
   - Socket: localhost:9876

4. Then restart your MCP client (e.g., restart Claude Code)
================================================================================
"""

    async def disconnect(self) -> None:
        """Close connection to FreeCAD XML-RPC server."""
        self._proxy = None
        self._transport = None
        self._connected = False
        self._shutdown_executor()

    def _shutdown_executor(self) -> None:
        """Stop accepting XML-RPC calls and release executor resources."""
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    async def _run_proxy_call(
        self,
        call: Callable[[xmlrpc.client.ServerProxy], Any],
        timeout_seconds: float,
    ) -> Any:
        """Run one serialized call against the shared XML-RPC proxy.

        ``ServerProxy`` transports are not thread-safe. A dedicated single-worker
        executor also prevents a timed-out background call from overlapping the
        next request while its blocking socket operation finishes.

        Args:
            call: Blocking operation to invoke with the active proxy.
            timeout_seconds: Maximum time to await the blocking operation.

        Returns:
            The XML-RPC response.

        Raises:
            ConnectionError: If the bridge is disconnected.
            TimeoutError: If the response does not arrive before the deadline.
        """
        if self._proxy is None or self._executor is None:
            msg = "Not connected to XML-RPC server"
            raise ConnectionError(msg)

        transport = self._transport

        def invoke(proxy: xmlrpc.client.ServerProxy) -> Any:
            if transport is not None:
                transport._timeout = timeout_seconds
            return call(proxy)

        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._executor, invoke, self._proxy)
        return await asyncio.wait_for(future, timeout=timeout_seconds)

    async def is_connected(self) -> bool:
        """Check if bridge is connected to FreeCAD."""
        if not self._connected or self._proxy is None:
            return False

        try:
            await self.ping()
            return True
        except Exception:
            self._connected = False
            return False

    async def ping(self) -> float:
        """Ping FreeCAD to check connection and measure latency.

        Returns:
            Round-trip time in milliseconds.

        Raises:
            ConnectionError: If not connected.
        """
        if self._proxy is None:
            msg = "Not connected to XML-RPC server"
            raise ConnectionError(msg)

        start = time.perf_counter()

        try:
            await self._run_proxy_call(
                lambda proxy: proxy.execute("_result_ = True"),
                self._timeout,
            )
        except TimeoutError as e:
            msg = "Ping timed out"
            raise ConnectionError(msg) from e
        except Exception as e:
            msg = f"Ping failed: {e}"
            raise ConnectionError(msg) from e

        return (time.perf_counter() - start) * 1000

    async def get_status(self) -> ConnectionStatus:
        """Get detailed connection status.

        Returns:
            ConnectionStatus with full status information.
        """
        if not self._connected or self._proxy is None:
            return ConnectionStatus(
                connected=False,
                mode="xmlrpc",
                error="Not connected",
            )

        try:
            ping_ms = await self.ping()
            version_info = await self.get_freecad_version()
            gui_available = await self.is_gui_available()

            return ConnectionStatus(
                connected=True,
                mode="xmlrpc",
                freecad_version=version_info.get("version", "unknown"),
                gui_available=gui_available,
                last_ping_ms=ping_ms,
            )
        except Exception as e:
            return ConnectionStatus(
                connected=False,
                mode="xmlrpc",
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
        """Execute Python code in FreeCAD context via XML-RPC.

        Args:
            code: Python code to execute.
            timeout_ms: Optional per-call timeout in milliseconds. The configured
                bridge default applies when omitted.

        Returns:
            ExecutionResult with execution outcome.
        """
        if self._proxy is None:
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="Not connected to XML-RPC server",
                execution_time_ms=0,
                error_type="ConnectionError",
            )

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
            response_timeout = (
                effective_timeout_ms / 1000 + EXECUTION_RESPONSE_GRACE_SECONDS
            )
            try:
                result = await self._run_proxy_call(
                    lambda proxy: proxy.execute(code, effective_timeout_ms),
                    response_timeout,
                )
            except xmlrpc.client.Fault as e:
                if not _is_legacy_execute_arity_fault(e):
                    raise
                result = await self._run_proxy_call(
                    lambda proxy: proxy.execute(code),
                    response_timeout,
                )
            elapsed = (time.perf_counter() - start) * 1000

            # Parse result from XML-RPC server
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
                # Simple result format
                return ExecutionResult(
                    success=True,
                    result=result,
                    stdout="",
                    stderr="",
                    execution_time_ms=elapsed,
                )

        except TimeoutError:
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr=(
                    f"Execution timed out after {effective_timeout_ms}ms; "
                    "code already running in FreeCAD may continue"
                ),
                execution_time_ms=float(effective_timeout_ms),
                error_type="TimeoutError",
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            return ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr=str(e),
                execution_time_ms=elapsed,
                error_type=type(e).__name__,
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

# Wrap in transaction for undo support
doc.openTransaction("Create Object")
try:
    obj = doc.addObject({type_id!r}, {name!r} or "")

    # Set properties
    for prop_name, prop_val in {properties!r}.items():
        if hasattr(obj, prop_name):
            setattr(obj, prop_name, prop_val)

    doc.recompute()
    doc.commitTransaction()
except Exception:
    doc.abortTransaction()
    raise

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

# Wrap in transaction for undo support
doc.openTransaction("Edit Object")
try:
    # Set properties
    for prop_name, prop_val in {properties!r}.items():
        if hasattr(obj, prop_name):
            setattr(obj, prop_name, prop_val)

    doc.recompute()
    doc.commitTransaction()
except Exception:
    doc.abortTransaction()
    raise

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

# Wrap in transaction for undo support
doc.openTransaction("Delete Object")
try:
    doc.removeObject({obj_name!r})
    doc.commitTransaction()
except Exception:
    doc.abortTransaction()
    raise

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
        """Capture a screenshot of the 3D view via XML-RPC."""
        view_angle_str = view_angle.value if view_angle else "Isometric"
        code = build_screenshot_code(doc_name, view_angle_str, width, height)
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
    _result_ = True  # Silently succeed in headless mode
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

# Get macro paths
macro_paths = []

# User macro path
user_path = FreeCAD.getUserMacroDir(True)
if os.path.exists(user_path):
    macro_paths.append(("user", user_path))

# System macro path
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
                "name": filename[:-8],  # Remove .FCMacro
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

# Find macro file
macro_name = {macro_name!r}
macro_file = None

# Check user macros first
user_path = FreeCAD.getUserMacroDir(True)
user_macro = os.path.join(user_path, macro_name + ".FCMacro")
if os.path.exists(user_macro):
    macro_file = user_macro

# Check system macros
if not macro_file:
    system_path = FreeCAD.getResourceDir() + "Macro"
    system_macro = os.path.join(system_path, macro_name + ".FCMacro")
    if os.path.exists(system_macro):
        macro_file = system_macro

if not macro_file:
    raise FileNotFoundError(f"Macro not found: {{macro_name}}")

# Set up arguments
args = {args!r}
for k, v in args.items():
    exec(f"{{k}} = {{v!r}}")

# Execute macro
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
    # Return common workbenches for headless mode
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
    _result_ = True  # Silently succeed in headless mode
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
# Try to get console output from FreeCAD
output_lines = []

# Try FreeCAD.Console if available
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
