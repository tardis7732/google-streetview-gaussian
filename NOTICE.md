# Source and dependency notes

- Reconstruction backend: [tardis7732/streetview-to-ply](https://github.com/tardis7732/streetview-to-ply), tested commit `3211651201467682ebdd92e3c81504234be5c468`. The cube sampler in `cubemap.py` is adapted from the same owner's `tools/streetview_engine/panorama_cube.py`; its attribution remains in the file. Other backend code is imported from a separate checkout, not bundled here.
- Optional Google metadata/download/label adapter: [YellowO2/streetview-to-3d](https://github.com/YellowO2/streetview-to-3d), commit `56fedd8efe3bf63e8bcdf5625cd9da67d9b6375c`. That project has its own MIT license and additional dependencies. Its code and model weights are not vendored in this repository.
- Web viewer dependencies: [Three.js](https://github.com/mrdoob/three) `0.180.0` and [Spark](https://github.com/sparkjsdev/spark) `2.4.0`, loaded from their versioned CDN URLs. Their projects maintain their own licensing.
- GPU reconstruction uses separately installed Brush, PyCOLMAP, PyTorch, and gsplat. Model/renderer/source licensing remains with each upstream project.
- Source Google Street View imagery, imagery-derived previews, trained scene files, weights, SSH configuration, authentication material, and generated edit images are not distributed here.

This repository has not assigned a separate redistribution license yet. It does not relicense upstream projects, models, or imagery.
