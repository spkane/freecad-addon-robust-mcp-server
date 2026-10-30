"""Tests for document tools module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from freecad_mcp.bridge.base import DocumentInfo, ExecutionResult


class TestDocumentTools:
    """Tests for document management tools."""

    @pytest.fixture
    def mock_mcp(self):
        """Create a mock MCP server that captures tool registrations."""
        mcp = MagicMock()
        mcp._registered_tools = {}

        def tool_decorator():
            def wrapper(func):
                mcp._registered_tools[func.__name__] = func
                return func

            return wrapper

        mcp.tool = tool_decorator
        return mcp

    @pytest.fixture
    def mock_bridge(self):
        """Create a mock FreeCAD bridge."""
        return AsyncMock()

    @pytest.fixture
    def register_tools(self, mock_mcp, mock_bridge):
        """Register document tools and return the registered functions."""
        from freecad_mcp.tools.documents import register_document_tools

        async def get_bridge():
            return mock_bridge

        register_document_tools(mock_mcp, get_bridge)
        return mock_mcp._registered_tools

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, register_tools, mock_bridge):
        """list_documents should return empty list when no documents."""
        mock_bridge.get_documents = AsyncMock(return_value=[])

        list_documents = register_tools["list_documents"]
        result = await list_documents()

        assert result == []
        mock_bridge.get_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_documents_with_docs(self, register_tools, mock_bridge):
        """list_documents should return document info."""
        mock_docs = [
            DocumentInfo(
                name="Doc1",
                label="Document 1",
                path="/tmp/doc1.FCStd",
                objects=["Box", "Cylinder"],
                is_modified=False,
                active_object="Box",
            ),
            DocumentInfo(
                name="Doc2",
                label="Document 2",
                path=None,
                objects=["Sphere"],
                is_modified=True,
                active_object=None,
            ),
        ]
        mock_bridge.get_documents = AsyncMock(return_value=mock_docs)

        list_documents = register_tools["list_documents"]
        result = await list_documents()

        assert len(result) == 2
        assert result[0]["name"] == "Doc1"
        assert result[0]["object_count"] == 2
        assert result[0]["is_modified"] is False
        assert result[1]["name"] == "Doc2"
        assert result[1]["object_count"] == 1
        assert result[1]["is_modified"] is True

    @pytest.mark.asyncio
    async def test_get_active_document_none(self, register_tools, mock_bridge):
        """get_active_document should return None when no active document."""
        mock_bridge.get_active_document = AsyncMock(return_value=None)

        get_active_document = register_tools["get_active_document"]
        result = await get_active_document()

        assert result is None
        mock_bridge.get_active_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_document_returns_info(self, register_tools, mock_bridge):
        """get_active_document should return document info when available."""
        mock_doc = DocumentInfo(
            name="ActiveDoc",
            label="Active Document",
            path="/tmp/active.FCStd",
            objects=["Part1", "Part2"],
            is_modified=True,
            active_object="Part1",
        )
        mock_bridge.get_active_document = AsyncMock(return_value=mock_doc)

        get_active_document = register_tools["get_active_document"]
        result = await get_active_document()

        assert result["name"] == "ActiveDoc"
        assert result["label"] == "Active Document"
        assert result["objects"] == ["Part1", "Part2"]
        assert result["is_modified"] is True

    @pytest.mark.asyncio
    async def test_create_document_default_name(self, register_tools, mock_bridge):
        """create_document should create with default name."""
        mock_doc = DocumentInfo(
            name="Unnamed",
            label="Unnamed",
            path=None,
            objects=[],
            is_modified=False,
        )
        mock_bridge.create_document = AsyncMock(return_value=mock_doc)

        create_document = register_tools["create_document"]
        result = await create_document()

        assert result["name"] == "Unnamed"
        mock_bridge.create_document.assert_called_once_with("Unnamed", None)

    @pytest.mark.asyncio
    async def test_create_document_with_name_and_label(
        self, register_tools, mock_bridge
    ):
        """create_document should use provided name and label."""
        mock_doc = DocumentInfo(
            name="MyPart",
            label="My Part Design",
            path=None,
            objects=[],
            is_modified=False,
        )
        mock_bridge.create_document = AsyncMock(return_value=mock_doc)

        create_document = register_tools["create_document"]
        result = await create_document(name="MyPart", label="My Part Design")

        assert result["name"] == "MyPart"
        assert result["label"] == "My Part Design"
        mock_bridge.create_document.assert_called_once_with("MyPart", "My Part Design")

    @pytest.mark.asyncio
    async def test_open_document(self, register_tools, mock_bridge):
        """open_document should open and return document info."""
        mock_doc = DocumentInfo(
            name="OpenedDoc",
            label="Opened Document",
            path="/tmp/test.FCStd",
            objects=["Box", "Fillet"],
            is_modified=False,
        )
        mock_bridge.open_document = AsyncMock(return_value=mock_doc)

        open_document = register_tools["open_document"]
        result = await open_document(path="/tmp/test.FCStd")

        assert result["name"] == "OpenedDoc"
        assert result["path"] == "/tmp/test.FCStd"
        assert result["objects"] == ["Box", "Fillet"]
        mock_bridge.open_document.assert_called_once_with("/tmp/test.FCStd")

    @pytest.mark.asyncio
    async def test_save_document_default(self, register_tools, mock_bridge):
        """save_document should save active document."""
        mock_bridge.save_document = AsyncMock(return_value="/tmp/saved.FCStd")

        save_document = register_tools["save_document"]
        result = await save_document()

        assert result["success"] is True
        assert result["path"] == "/tmp/saved.FCStd"
        mock_bridge.save_document.assert_called_once_with(None, None)

    @pytest.mark.asyncio
    async def test_save_document_with_path(self, register_tools, mock_bridge):
        """save_document should save to specified path."""
        mock_bridge.save_document = AsyncMock(return_value="/new/path.FCStd")

        save_document = register_tools["save_document"]
        result = await save_document(doc_name="MyDoc", path="/new/path.FCStd")

        assert result["success"] is True
        assert result["path"] == "/new/path.FCStd"
        mock_bridge.save_document.assert_called_once_with("MyDoc", "/new/path.FCStd")

    @pytest.mark.asyncio
    async def test_close_document_without_save(self, register_tools, mock_bridge):
        """close_document should close without saving by default."""
        mock_bridge.close_document = AsyncMock()

        close_document = register_tools["close_document"]
        result = await close_document(doc_name="TestDoc")

        assert result["success"] is True
        assert result["saved"] is False
        mock_bridge.close_document.assert_called_once_with("TestDoc")

    @pytest.mark.asyncio
    async def test_close_document_with_save(self, register_tools, mock_bridge):
        """close_document should save before closing when requested."""
        mock_bridge.save_document = AsyncMock(return_value="/tmp/doc.FCStd")
        mock_bridge.close_document = AsyncMock()

        close_document = register_tools["close_document"]
        result = await close_document(doc_name="TestDoc", save_changes=True)

        assert result["success"] is True
        assert result["saved"] is True
        mock_bridge.save_document.assert_called_once_with("TestDoc")
        mock_bridge.close_document.assert_called_once_with("TestDoc")

    @pytest.mark.asyncio
    async def test_close_document_save_failure(self, register_tools, mock_bridge):
        """close_document should still close even if save fails."""
        mock_bridge.save_document = AsyncMock(side_effect=Exception("Save failed"))
        mock_bridge.close_document = AsyncMock()

        close_document = register_tools["close_document"]
        result = await close_document(doc_name="TestDoc", save_changes=True)

        assert result["success"] is True
        assert result["saved"] is False
        mock_bridge.close_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_recompute_document_success(self, register_tools, mock_bridge):
        """recompute_document should return success on recompute."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={"success": True, "invalid_objects": []},
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )

        recompute_document = register_tools["recompute_document"]
        result = await recompute_document(doc_name="TestDoc")

        assert result["success"] is True
        assert result.get("error") is None
        mock_bridge.execute_python.assert_called_once()

    @pytest.mark.asyncio
    async def test_recompute_reports_invalid_objects(self, register_tools, mock_bridge):
        """A completed RPC does not imply every object recomputed successfully."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=True,
                result={
                    "success": False,
                    "invalid_objects": [
                        {"name": "Sketch", "label": "Text", "state": ["Invalid"]}
                    ],
                },
                stdout="",
                stderr="",
                execution_time_ms=5.0,
            )
        )
        result = await register_tools["recompute_document"](doc_name="TestDoc")
        assert result["success"] is False
        assert result["invalid_objects"][0]["name"] == "Sketch"
        assert result["error"]

    @pytest.mark.asyncio
    async def test_recompute_document_failure(self, register_tools, mock_bridge):
        """recompute_document should return error on failure."""
        mock_bridge.execute_python = AsyncMock(
            return_value=ExecutionResult(
                success=False,
                result=None,
                stdout="",
                stderr="",
                execution_time_ms=5.0,
                error_type="ValueError",
                error_traceback="No document found",
            )
        )

        recompute_document = register_tools["recompute_document"]
        result = await recompute_document(doc_name="NonExistent")

        assert result["success"] is False
        assert result["error"] == "No document found"
