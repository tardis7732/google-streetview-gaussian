# 입출력 구조

```text
runs/area/
  area_survey.json             # center, radius_m, required_date, accepted, inspected
  photo_paths.json             # panorama ID -> local original photograph path
  photos/                     # original equirectangular photographs
  labels/                     # road/protection label PNGs, no RGB removal
  labels_complete.json
  reconstruction/
    selection.json
    prepared/manifest.json    # six fixed 90-degree views per physical station
    sfm/                      # native visual/GPS reports and calibrated dataset
    training/dataset/         # OpenGL c2w; EDN world, metres
    training/refined/final.ply
  ground_ready.npz             # points (EDN) and RGB converted to SH0
  ground_support.npy
  output/model.ply             # fused model
  output/manifest.json
  holefix/model.ply            # append-only ground gap repair
  holefix/manifest.json
```

원본 사진은 각 사용자의 로컬 데이터입니다. `photo_paths.json` may contain absolute local paths; it belongs to a run, not to the source repository.

## Viewer export

```text
runs/viewer/
  manifest.json
  panorama_index.json
  model.ply                   # actual basename is manifest.model_file
  panoramas/<pano_id>.jpg
```

`manifest.json` needs `model_file`, `gaussians`, `date` (`YYYY-MM`), and `sources`. Each source has `id`, `date`, `lat`, `lon`, and `camera_world` in EDN metres. The viewer maps EDN to its east/up/south convention by `(x, -y, -z)`.

`panorama_index.json` contains the corresponding sources, their relative `file` paths, and a row-major `world_to_pano_cv` 3×3 rotation. Original spherical rays use +X right, +Y down and +Z forward. This rotation is derived from the visually registered front camera, not from a hardcoded geographic heading.

The source PNG/JPG pixels are sampled at the nearest physical capture position. The viewer copies the virtual camera's **orientation and field of view** for reference export; it does not translate the panorama origin or synthesize unseen parallax.

## Previous hybrid ground

`ground --legacy folder` expects a Gaussian PLY and `manifest.json` containing `sources[].camera_world`, `hybrid.new_ground_vertex_start` and `hybrid.new_ground_splats`. The model basename is taken from `model_file`, then `hybrid.final_filename`, then `hybrid_final.ply`. The first ground layer and shared visual camera centers are aligned by a fitted similarity; local new-run ground constraints still apply.
