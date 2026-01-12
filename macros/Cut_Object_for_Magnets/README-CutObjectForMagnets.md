# Cut Object for Magnets - FreeCAD Macro

![Macro Icon](CutObjectForMagnets.svg)

**Version:** 0.6.0
**FreeCAD Version:** 0.19 or later
**License:** MIT

> **Documentation:** [https://spkane.github.io/freecad-robust-mcp-and-more/](https://spkane.github.io/freecad-robust-mcp-and-more/)

## Overview

This FreeCAD macro intelligently cuts 3D objects along a plane and automatically places magnet holes (for magnets, dowels, pins, etc.) with built-in surface penetration detection. Unlike simple cutting tools, this macro ensures magnet holes won't accidentally break through the outer surface of your object.

Perfect for creating multi-part prints that snap together with magnets or alignment pins!

## Quick Visual Guide

### Method 1: Preset Planes (Simple)

```text
Select Object → Run Macro → Choose XY/XZ/YZ → Set Offset → Execute
```

Use for: Axis-aligned cuts, quick splits, standard orientations

### Method 2: Model Planes (Advanced - ANY Angle)

```text
Create Datum Plane (angled as needed) → Select Object → Run Macro →
Choose "Model Plane" → Select Your Plane → Execute
```

Use for: Angled cuts, following model geometry, complex orientations

### Quick Tip: Select Both Object AND Plane Together

```text
Select Object + Plane (Ctrl+Click) → Run Macro → Plane auto-selected!
```

The macro automatically detects when you select both an object and a plane together.

---

## Features

- **Smart Surface Detection** - Automatically skips holes that would penetrate the object's outer surface
- **Smart Repositioning** - When a hole would penetrate, tries nearby positions (further inward or along perimeter)
- **Dual-Part Validation** - Validates each hole position works for BOTH parts before creating any holes
- **Minimum Spacing** - Ensures holes are at least 2x diameter apart (one hole width between them)
- **Automatic Alignment** - Magnet holes on both pieces are perfectly aligned
- **Flexible Plane Selection** - Use preset planes (XY/XZ/YZ) OR any datum plane/face from your model
- **Angled Cuts** - Cut along any angle by selecting a datum plane
- **Even Distribution** - Holes are evenly spaced around the perimeter of the cut face
- **Count-Based Placement** - Specify exact number of holes (default: 6) for precise control
- **Safety Clearance** - Maintains minimum distance from outer surfaces
- **Visual Feedback** - Progress bar and status messages
- **Non-Destructive** - Original object is hidden, not deleted

---

## Installation

### macOS Installation (Detailed)

#### Step 1: Locate Your FreeCAD Macros Folder

The macros folder location on macOS:

```text
~/Library/Application Support/FreeCAD/Macro/
```

**How to access it:**

**Option A - Finder (Recommended):**

1. Open **Finder**
1. Press `Cmd + Shift + G` (Go to Folder)
1. Paste: `~/Library/Application Support/FreeCAD/Macro/`
1. Press **Enter**

**Option B - Terminal:**

```bash
mkdir -p ~/Library/Application\ Support/FreeCAD/Macro/
open ~/Library/Application\ Support/FreeCAD/Macro/
```

**Option C - From FreeCAD:**

1. Open FreeCAD
1. Go to **Macro → Macros...**
1. Note the path shown at the top of the dialog
1. Click **User macros location** to open in Finder

#### Step 2: Install the Macro File

1. Save the macro file as `CutObjectForMagnets.FCMacro` in the macros folder
1. (Optional) Save the icon as `CutObjectForMagnets.svg` in the same folder

#### Step 3: Verify Installation

1. Open FreeCAD
1. Go to **Macro → Macros...**
1. You should see "CutObjectForMagnets" in the list
1. (Optional) Click **Edit** to view the macro code

#### Step 4: Create a Toolbar Button (Optional but Recommended)

1. Go to **Macro → Macros...**
1. Select **CutObjectForMagnets**
1. Click **Create** (toolbar button icon)
1. Choose the icon file (`CutObjectForMagnets.svg`) if you saved it
1. The macro will now appear in your toolbar for quick access

---

### Linux Installation

```bash
# Create macros directory if it doesn't exist
mkdir -p ~/.FreeCAD/Macro/

# Copy macro file
cp CutObjectForMagnets.FCMacro ~/.FreeCAD/Macro/

# (Optional) Copy icon
cp CutObjectForMagnets.svg ~/.FreeCAD/Macro/
```

---

### Windows Installation

1. Navigate to: `%APPDATA%\FreeCAD\Macro\`
1. Copy `CutObjectForMagnets.FCMacro` to this folder
1. (Optional) Copy `CutObjectForMagnets.svg` to the same folder

---

## How to Use

### Quick Start Guide

#### Step 1: Prepare Your Model

1. Open your model in FreeCAD (or create/import one)
1. Ensure the object is a **solid** (not a shell or surface)
1. **Select the object** in the 3D view or tree view

**Tip:** If you imported an STL, it should already be a valid solid. If you created the model in FreeCAD, make sure you created a solid object in the Part workbench.

#### Step 2: Launch the Macro

- **From Macro Menu:** Macro → Macros... → Select "CutObjectForMagnets" → Execute
- **From Toolbar:** Click the macro icon (if you created a toolbar button)

#### Step 3: Configure Cut Plane

The dialog will open with several configuration sections.

**Plane Type Settings:**

You have two options for defining your cut plane:

**Option 1: Preset Plane** (Simple, axis-aligned cuts)

- **Plane:** Choose orientation

  - `XY` - Horizontal cut (most common)
  - `XZ` - Vertical cut (front-to-back)
  - `YZ` - Vertical cut (left-to-right)

- **Offset:** Position of the cut plane from origin (in mm)

  - `0` - Cut through the origin
  - Positive values move the plane in the positive axis direction
  - Negative values move it in the negative axis direction

**Finding the Right Offset:**

1. Note your object's bounding box dimensions (visible in FreeCAD)
1. If your object is centered at origin and you want to cut in half:
   - Use offset = `0`
1. If your object is positioned elsewhere:
   - Look at the coordinate where you want to cut
   - Use that value as the offset

**Option 2: Model Plane** (Advanced, angled cuts)

Select any datum plane or planar face from your model:

**Using Datum Planes:**

1. Create a datum plane first (if not already in model):

   - Go to **Part Design** workbench
   - Click **Create datum plane** (or Part → Datum → Datum Plane)
   - Position and angle the plane where you want to cut
   - Exit datum plane creation

1. In the macro dialog:

   - Select **"Model Plane"** from Plane Type
   - Choose your datum plane from the dropdown
   - The offset field is disabled (plane position defines the cut)

**Using Object Faces:**

- Any planar face on any object in your document can be used as a cut plane
- Select from the dropdown: "Face: [ObjectName] (Face1, Face2, etc.)"
- Useful for cutting along existing geometry

**Examples of Model Plane Cuts:**

- Cut at 45° angle - Create datum plane rotated 45° around X or Y axis
- Cut following surface contour - Select a planar face on reference geometry
- Cut perpendicular to cylinder axis - Use cylinder end face
- Complex multi-angle cuts - Create multiple datum planes for different cuts

#### Step 4: Configure Magnet Holes

**Hole Parameters:**

- **Diameter:** The diameter of your magnet (mm)

  - For 6mm magnets: Use `6.2mm` (adds 0.2mm clearance)
  - For 3mm dowels: Use `3.1mm` (adds 0.1mm clearance)
  - For friction fit: Use exact diameter or slightly smaller

- **Depth:** How deep holes go into each piece (mm)

  - For magnets: Use magnet thickness + 0.5mm
  - For dowel pins: Usually half the dowel length
  - **Important:** Each piece gets this depth

- **Number of Holes:** Total number of magnet holes to create (default: 6)

  - Holes are evenly distributed around the perimeter of the cut face
  - More holes = stronger joint, but requires more magnets
  - Recommended: `4-6` for small objects, `8-12` for large objects

- **Edge Clearance (Preferred):** Ideal distance from hole edge to outer surface (mm)

  - Default: `2mm` - holes are initially placed with this clearance
  - This is the distance the macro tries to maintain for optimal part strength
  - Larger values = more material around holes = stronger parts

- **Edge Clearance (Minimum):** Absolute minimum acceptable clearance (mm)

  - Default: `0.5mm` - the smallest allowable clearance
  - When smart repositioning can't place a hole at preferred clearance, it will try progressively smaller clearances down to this minimum
  - Prevents holes from getting too close to outer surfaces
  - For thin-walled objects: Increase this value to prevent breakthrough

#### Step 5: Execute the Cut

1. Review all parameters
1. Click **"Execute Cut"**
1. Watch the progress bar
1. Check status messages for any skipped holes

#### Step 6: Review Results

The macro creates two new objects:

- `[ObjectName]_Bottom` - Lower piece with holes
- `[ObjectName]_Top` - Upper piece with holes

Your original object is **hidden** (not deleted) - you can show it again from the tree view if needed.

---

## Parameter Reference Guide

### Understanding Edge Clearance

The macro uses a **dual clearance system** to balance ideal hole placement with flexibility:

- **Preferred Clearance (2mm default):** Initial hole placement uses this value
- **Minimum Clearance (0.5mm default):** Fallback when preferred clearance fails

**How it works:**

1. Holes are first placed using the preferred clearance
1. If a hole fails the safety check at preferred clearance, smart repositioning kicks in
1. The macro tries progressively smaller clearances (from preferred down to minimum)
1. Only if all clearance levels fail does the macro try moving the hole position

The safety check ensures:

```text
hole_radius + depth + clearance < distance_to_nearest_surface
```

**Visual Example:**

```text
    [Outer Surface]
         |
    clearance (preferred: 2mm, min: 0.5mm)
         |
    [Hole boundary]  ← Must not touch outer surface
         |
    actual hole
```

If a hole would violate even the minimum clearance, it's automatically skipped and you'll see a warning in the console.

### Calculating Depth for Magnets

For magnets that should be flush or recessed:

```text
depth = magnet_thickness + recess_amount

Examples:
- 2mm thick magnet, flush: depth = 2.5mm (0.5mm tolerance)
- 3mm thick magnet, 0.5mm recess: depth = 3.5mm + 0.5mm = 4mm
```

**Important:** Total depth in both pieces should accommodate the magnet fully:

```text
total_depth = depth_bottom + depth_top
total_depth should be >= magnet_thickness
```

### Recommended Hole Count Guidelines

| Object Size       | Recommended Holes | Notes                              |
| ----------------- | ----------------- | ---------------------------------- |
| Small (\<50mm)    | 4-6               | Fewer holes for small surfaces     |
| Medium (50-150mm) | 6-10              | Default of 6 works well            |
| Large (>150mm)    | 10-16             | More holes for stronger connection |
| Thin-walled       | 4-6               | Use smaller diameter holes         |

---

## Common Use Cases

### Case 1: Large Print Split for Bed Size

**Scenario:** 300mm diameter object, need to split for 250mm print bed

**Settings:**

```text
Plane: XY
Offset: 0 (if centered) or half the object height
Diameter: 6.2mm (for 6×2mm magnets)
Depth: 2.5mm
Number of Holes: 12
Clearance: 3mm
```

**Result:** Two pieces that stack vertically with 12 evenly-spaced magnets for alignment

---

### Case 2: Modular Terrain Tiles

**Scenario:** 100×100mm terrain tiles with magnetic edges

**Settings:**

```text
Plane: XY or YZ (depending on desired split)
Offset: 50mm (half the tile dimension)
Diameter: 3.2mm (for 3×1mm magnets)
Depth: 1.5mm
Number of Holes: 6
Clearance: 2mm
```

**Result:** Tiles that connect magnetically at edges with 6 evenly-spaced magnets

---

### Case 3: Dowel Pin Alignment for Large Parts

**Scenario:** Splitting a large miniature or sculpture

**Settings:**

```text
Plane: XY
Offset: [at desired split point]
Diameter: 3.1mm (for 3mm brass pins)
Depth: 8mm (16mm pins, 8mm per side)
Number of Holes: 4
Clearance: 3mm
```

**Result:** Precise alignment with 4 evenly-spaced removable pins

---

### Case 4: Angled Cut with Datum Plane (45° Wedge)

**Scenario:** Splitting a wedge-shaped console at a 45° angle

**Preparation:**

1. Switch to **Part Design** workbench
1. Create datum plane:
   - Click **Create datum plane** (or Part → Datum → Create datum plane)
   - In the dialog:
     - Attachment mode: "Translate origin"
     - Angle: Rotate 45° around X-axis
     - Position: Move to desired cut location
   - Click **OK**
1. Name it "CutPlane45" (optional but helpful)

**Settings:**

```text
Plane Type: Model Plane
Model Plane: Plane: CutPlane45
Diameter: 6.2mm (for 6×2mm magnets)
Depth: 3mm
Number of Holes: 8
Clearance: 3mm
```

**Result:** Clean 45° angled cut with 8 evenly-spaced magnet holes

**Pro Tip:** You can visually see where the cut will be by looking at the datum plane position before running the macro!

---

## Troubleshooting

### Error: "Please select an object to cut"

**Solution:** Click on your object in the 3D view before running the macro.

---

### Error: "Selected object does not have a shape"

**Solution:** You selected a group or annotation. Select the actual 3D object (should be under Part or Body in the tree).

---

### Error: "Failed to cut object"

**Possible causes:**

1. **Invalid mesh** - The object has geometry errors

   - Try: Edit → Preferences → Part Design → "Automatically refine model after boolean operation"
   - Or manually: Part → Refine Shape

1. **Offset is outside object bounds** - The cut plane doesn't intersect the object

   - Check your object's position and bounding box
   - Adjust offset to actually pass through the object

1. **Model plane doesn't intersect** - The selected datum plane or face doesn't pass through the object

   - Verify the plane position in the 3D view
   - Create a new datum plane that actually cuts through the object

---

### Error: "No planes available"

**Solution:** You selected "Model Plane" but no datum planes or planar faces exist in the document.

**Fix:**

1. Create a datum plane:
   - **Part Design → Create datum plane**
   - Position and angle as needed
   - Click OK
1. Or switch to "Preset Plane" mode
1. Re-run the macro

---

### Warning: "Skipping hole at [position] - would penetrate surface"

**This is normal!** The macro is protecting you from holes that would break through.

**If too many holes are skipped:**

1. **Increase edge clearance** (e.g., from 2mm to 4mm)
1. **Increase spacing** (fewer holes, but safer)
1. **Reduce hole depth** (less likely to penetrate)
1. **Check your object** - might be too thin for the hole size

---

### Error: "No valid hole positions found"

**Possible causes:**

1. **Cut surface too small** - Not enough room for even one hole

   - Solution: Reduce spacing or hole diameter

1. **Object too thin** - All positions would penetrate

   - Solution: Reduce hole depth or increase clearance less aggressively

1. **Complex geometry** - Cut surface is irregular

   - Solution: Manually place holes in FreeCAD after cutting

---

## Advanced Tips & Best Practices

### Creating Perfect Datum Planes

**For Angled Cuts:**

1. **Simple Rotation Method:**

   ```text
   Part Design → Create datum plane
   - Reference: XY plane (or any base plane)
   - Attachment offset → Rotation:
     - Around X: Tilts forward/back
     - Around Y: Tilts left/right
     - Around Z: Spins horizontally
   - Position: Translation Z/Y/X to move the plane
   ```

1. **Align to Edges/Vertices:**

   ```text
   Part Design → Create datum plane
   - Attachment mode: "Three points"
   - Select 3 points on your model
   - Plane will pass through all three points
   ```

### Choosing the Right Clearance

The dual clearance system gives you fine-grained control:

**Preferred Clearance (default 2mm):**

- Sets how far from edges holes are initially placed
- Increase for stronger parts (more material around holes)
- Decrease if you need holes closer to edges

**Minimum Clearance (default 0.5mm):**

- The absolute minimum acceptable distance from edges
- Increase for thin-walled objects to prevent breakthrough
- Should always be ≤ preferred clearance

**Guidelines by object type:**

- **Thin-walled objects** (2-4mm walls): Preferred=2mm, Minimum=1mm
- **Thick objects** (>10mm walls): Preferred=3mm, Minimum=0.5mm (defaults work well)
- **Irregular shapes:** Preferred=4-5mm, Minimum=2mm to be safe

### Magnet Installation Tips

After printing and cutting:

1. Test fit magnets - they should slide in smoothly
1. If too tight: Use a drill bit to clean out the holes slightly
1. If too loose: Use CA glue or epoxy to secure
1. **Check polarity!** - Mark magnet orientation before gluing

---

## Technical Details

### How Surface Penetration Detection Works

For each potential hole position, the macro:

1. Creates a test cylinder with radius = `(diameter/2) + clearance`
1. Extends the cylinder to depth = `hole_depth + clearance`
1. Performs boolean intersection with the part
1. If intersection volume < 99% of test cylinder volume → hole would penetrate → skip it

This ensures holes only go where they're safe!

### Coordinate System

- **Origin (0,0,0):** FreeCAD document origin
- **Cut planes** pass through a point at the specified offset:
  - XY plane: Point = (0, 0, offset)
  - XZ plane: Point = (0, offset, 0)
  - YZ plane: Point = (offset, 0, 0)

### Hole Direction

- **Bottom piece:** Holes point UP (toward cut plane)
- **Top piece:** Holes point DOWN (toward cut plane)
- Both sets align perfectly at the cut interface

---

## Version History

### v0.5.0-beta (2026-01-05)

- Initial release
- XY, XZ, YZ preset plane support
- Model plane support (datum planes and planar faces)
- Angled cut capability via datum planes
- Surface penetration detection
- Configurable hole parameters
- Progress tracking
- Dual-part validation
- Minimum spacing enforcement (2x diameter)
- Smart hole repositioning
- Object selection combo box

---

## License

MIT License - Free to use, modify, and distribute.

---

## Credits

Created for the FreeCAD community to make multi-part 3D printing easier and more reliable.

**Inspiration:** PrusaSlicer's cut tool, but with reliable export and better surface detection.
