"""MCP prompt templates for FreeCAD.

This package contains reusable prompt templates for common FreeCAD tasks.
Prompts guide users through complex workflows and provide best practices.

Available prompts:
    Design Workflows:
        - design_part: Guided parametric part design
        - create_sketch_guide: 2D sketch creation
        - boolean_operations_guide: Shape combination

    Export/Import:
        - export_guide: Export to various formats
        - import_guide: Import from various formats

    Analysis:
        - analyze_shape: Shape geometry analysis
        - debug_model: Model troubleshooting

    Macro Development:
        - macro_development: Macro creation guide
        - python_api_reference: API quick reference

    Troubleshooting:
        - troubleshooting: General issue resolution
"""

from freecad_mcp.prompts.freecad import register_prompts

__all__ = ["register_prompts"]
