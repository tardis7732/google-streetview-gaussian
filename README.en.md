# Google Street View Gaussian

[한국어 / complete instructions](README.md)

An experimental toolkit for exact-month Google Street View collection, calibrated visual SfM, Brush/gsplat Gaussian reconstruction, local ground fusion, bounded ground-gap repair, and paired Gaussian/reference PNG capture.

The GPU reconstruction adapter uses a separately installed, pinned [streetview-to-ply](https://github.com/tardis7732/streetview-to-ply) checkout. Google collection uses the optional [YellowO2/streetview-to-3d](https://github.com/YellowO2/streetview-to-3d) adapter.

```bash
python -m pip install -e .
python -m google_streetview_gaussian --help
python -m google_streetview_gaussian crop --image panorama.png --output cropped.png --aspect 2.5
python -m google_streetview_gaussian panorama --image original.jpg --output opposite.png --aspect 2.5 --hfov 225
python -m google_streetview_gaussian viewer --data-dir runs/viewer
```

Python 3.11+ supports CPU tools and the local viewer; the Google adapter requires Python 3.12+. Reconstruction requires a Linux/WSL2 NVIDIA CUDA environment and separate model/backend installation. See [GPU setup](docs/GPU_SETUP.md).

The capture viewer exports UI-free Gaussian and nearest original Street View images with matching orientation, field of view, dimensions, and aspect. Its middle button saves both PNGs to the local Downloads directory without creating a ZIP. Translation is not synthesized: parallax remains when camera positions differ.

Panorama projection uses original photograph/cube pixels; aspect cropping does not resample pixels or use image generation. Ground repair interpolates estimated surfaces and, where occluded, neighboring road colors. It is not a new physical observation. People, vehicles, and sky are retained.

No source Street View imagery, trained Gaussian PLYs, model weights, or machine credentials are distributed in this repository. CPU tests cover date/radius enforcement, cube geometry, unchanged crop pixels, local plane fitting, ground/hybrid/repair/export, and paired PNG saving. The GPU pipeline has not been re-run end-to-end after this packaging refactor; the earlier H200 experiment is documented separately in [EXPERIMENT.md](docs/EXPERIMENT.md).

No redistribution license has been assigned to this repository yet. External dependencies retain their own licenses; see [NOTICE](NOTICE.md).
