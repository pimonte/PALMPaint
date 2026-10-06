# Trees in PALMPaint

## Single tree tool

Select **single_tree** in the toolbar. Left-click places a tree, right-click (or right-drag) removes it. Each tree is written as a 3D leaf area density (`lad`) and, if enabled, basal area density (`bad`). Ctrl+T shows or hides the tree overlay.

| Control | Meaning |
|---|---|
| Species | Preset species, loads geometry and LAD/BAD parameters |
| Shape | Crown shape: spherical, cylindrical, conical, inverse conical, paraboloid, inverse paraboloid |
| H/D ratio | Crown height / crown diameter, larger means a taller crown |
| Crown Diam. (m) | Horizontal crown diameter, also the size of the preview circle |
| Tree Height (m) | Total height from the ground to the crown tip |
| LAI | Leaf area index (m2/m2), scales the total leaf area |
| BAD/LAD | Ratio of branch area density to leaf area density |
| Trunk Diam. (m) | Trunk diameter at breast height |
| Write BAD | Write the `bad` array into the file |

Leaves are never placed in or above a building (like palm_csd), a crown over a roof is cut at the wall.

### BAD field

BAD describes the drag of branches and trunk (not used by PALM yet):

- Trunk: 1.0 m2/m3 from the ground to mid-crown, only if the trunk is at least one grid cell wide.
- Crown, `palm_extinction` model: BAD is highest where LAD is lowest (towards the inside of the crown), at most `bad_lad_ratio`.
- Crown, `beta_density` model: BAD follows LAD, at most `bad_lad_ratio`.

## Tree Generator (alpha)

The Tree Generator is new and may give unexpected results for unusual parameter combinations.

1. Select **single_tree** and click **Tree Generator...** in the top bar.
2. Set the parameters below.
3. Click **Apply to Brush**. The top bar shows "Generator: active".
4. Place trees as usual. **Clear Generator** goes back to the simple crown.

### Parameters

**Geometry**

| Parameter | Meaning |
|---|---|
| Max height (m) | Total tree height |
| Crown diameter (m) | Horizontal crown diameter, also the reference area for the LAI |
| Trunk diameter (m) | Trunk diameter below the crown |
| Crown aspect (H/D) | Crown height / crown diameter |
| Crown shape | 1 to 6: spherical, cylindrical, conical, inverse conical, paraboloid, inverse paraboloid |

**LAD model**

| Parameter | Meaning |
|---|---|
| LAD model | `beta_density` (beta distribution, default) or `palm_extinction` (radial decay like PALM) |
| Profile mode | Beta profile shapes the LAD with a fixed crown, or shapes the crown with a constant LAD |
| Alpha / Beta | Shape of the beta distribution of the vertical LAD profile |
| Extinction k | Decay for `palm_extinction`, like PALM's `tree_sphere_extinction` |
| BAD/LAD ratio | Maximum BAD in the crown relative to LAD |

**Scaling**: either LAI (m2/m2, leaf area per crown area) or LAD_max (m2/m3, peak density). The radio buttons switch between them.

### Preview and presets

With matplotlib installed, the dialog shows a live preview at 1 m resolution. Without it, everything else works.

**Save Preset** and **Load Preset** store all parameters as a JSON file (default folder `~/.config/palmpaint/presets/`).
