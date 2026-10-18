"""Container entrypoint. Dashboard reads only an already validated evidence artifact."""
from pathlib import Path
import os
from .server import create_app
app = create_app(Path(os.environ.get('OUTPUT', '/output/evidence.json')), Path('/output/concordance-phase3w.json'), Path('/output/clip-diagnostics.json'), Path('/output/product-readiness.json'), Path('/output/external-scene-probe.json'))
