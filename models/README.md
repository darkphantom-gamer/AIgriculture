# Models

AIgriculture ships two PyTorch models and one optional Hailo model for
on-device inference. All files live in this directory.

## Included

| File | Task | Size | Backend |
|------|------|------|---------|
| `Disease_detect.pt` | Strawberry disease detection (5 classes) | ~5 MB | CPU (default) |
| `Ripeness_detect.pt` | Fruit ripeness staging (5 stages) | ~6 MB | CPU (default) |
| `hailo/Finalized_disease_model.hef` | Disease detection compiled for Hailo-8 | ~4 MB | Hailo (optional) |

## Labels

Class names are in `labels/`:

- `farm_monitor_disease_labels.json` — disease class index → name
- `farm_monitor_ripeness_labels.json` — ripeness class index → name

## Swapping models

Pass custom model paths on the command line:

```bash
python -m aigriculture \
  --disease-model  /path/to/my_disease.pt \
  --ripeness-model /path/to/my_ripeness.pt
```

The models must be Ultralytics YOLO-compatible `.pt` files.

## Hailo models

Hailo `.hef` files are compiled for a specific chip revision.
The bundled `Finalized_disease_model.hef` targets Hailo-8 (H8).

To compile your own `.hef` from a `.pt`:

1. Export to ONNX: `yolo export model=Disease_detect.pt format=onnx`
2. Compile with the Hailo Dataflow Compiler (requires Hailo SDK):
   `hailo compile Disease_detect.onnx --target hailo8`

See [Hailo developer zone](https://hailo.ai/developer-zone/) for full
SDK docs and driver installation.
