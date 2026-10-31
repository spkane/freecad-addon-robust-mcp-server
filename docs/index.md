---
hide:
  - toc
---

# Build in FreeCAD with your AI assistant

<div class="landing" markdown>

<div class="landing-hero" markdown>
<div class="landing-hero__copy" markdown>

<span class="landing-eyebrow">FREECAD + MODEL CONTEXT PROTOCOL</span>

## From an idea to a model, together

Give your MCP-compatible assistant a direct connection to FreeCAD. Create and
inspect geometry, explore a design, and export your work while keeping FreeCAD
at the center of the workflow.

[Quick start](getting-started/quickstart.md){ .md-button .md-button--primary }
[Explore the tools](guide/tools.md){ .md-button }

<span class="landing-note">Open source · Local-first connection · GUI and headless modes</span>

</div>
<div class="landing-hero__visual" markdown>

![An example mounting bracket rendered in the FreeCAD 3D view](assets/images/bracket-example.webp)

<span class="landing-image-caption">EXAMPLE MODEL · FREECAD 3D VIEW</span>

</div>
</div>

<div class="landing-section-heading" markdown>

<span class="landing-eyebrow">A PRACTICAL CAD COMPANION</span>

## Work in the tools you already use

The server exposes FreeCAD operations to your assistant; the bridge workbench
runs inside FreeCAD and carries out those operations.

</div>

<div class="landing-grid" markdown>

<div class="landing-card" markdown>

### Create and edit

Build primitives and PartDesign features, combine geometry, and work with
documents and objects through natural-language requests.

</div>
<div class="landing-card" markdown>

### Inspect and iterate

Ask about objects and properties, adjust a model, and capture views in FreeCAD's
GUI to review the result as you work.

</div>
<div class="landing-card" markdown>

### Export and automate

Prepare STEP, STL, and other supported exports, or use headless FreeCAD for
workflows that do not need a visible 3D view.

</div>
</div>

<div class="landing-feature" markdown>
<div class="landing-feature__visual" markdown>

![An example bearing mount rendered in FreeCAD](assets/images/bearing-mount-example.webp)

<span class="landing-image-caption">EXAMPLE MODEL · FREECAD 3D VIEW</span>

</div>
<div class="landing-feature__copy" markdown>

<span class="landing-eyebrow">IDEAS TO TRY</span>

## Start with a useful request

- “Create a mounting bracket with four bolt holes.”
- “Inspect this part and tell me its dimensions and volume.”
- “Export the current model to STEP and STL.”
- “Show an isometric view and capture a screenshot.”

These are example requests; review the generated geometry and dimensions
before using a model for manufacturing.

[See the quick start](getting-started/quickstart.md) · [View all tools](guide/tools.md)

</div>
</div>

<div class="landing-section-heading" markdown>

<span class="landing-eyebrow">GET CONNECTED</span>

## Three pieces, one workflow

</div>
<div class="landing-steps" markdown>

<div markdown>

### 01 · Install

Install the MCP server and the Robust MCP Bridge workbench in FreeCAD. The
[quick start](getting-started/quickstart.md) walks through both installations.

</div>
<div markdown>

### 02 · Pair and start

Run `freecad-mcp --pair-bridge`, then start the bridge in FreeCAD.

</div>
<div markdown>

### 03 · Connect your assistant

Configure an MCP-compatible client and start with a small request.

</div>
</div>

<div class="landing-status" markdown>
<div markdown>

### See when the bridge is running

The workbench toolbar starts and stops the bridge. Its status indicator shows
when the local connection is available.

[Workbench guide](guide/workbench.md) · [Connection and security settings](getting-started/configuration.md)

</div>
<div class="landing-status__images" markdown>

![FreeCAD Robust MCP Bridge toolbar](assets/images/bridge-toolbar.png)

![FreeCAD bridge running status indicator](assets/images/bridge-status.png)

</div>
</div>

<div class="landing-bottom" markdown>

## Ready to connect?

Follow the quick start to set up FreeCAD, the bridge, and your MCP client.

[Get started](getting-started/quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/spkane/freecad-addon-robust-mcp-server){ .md-button }

</div>
</div>
