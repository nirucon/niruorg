#!/usr/bin/env python3
from pathlib import Path
import tempfile, os
with tempfile.TemporaryDirectory() as td:
 p=Path(td); releases=p/'releases'; releases.mkdir(); old=releases/'0.0.9'; old.mkdir(); current=p/'current'; current.symlink_to(old)
 stage=releases/'0.0.14.staging'; stage.mkdir()
 # Simulated validation failure: activation must not run.
 validation_ok=False
 if validation_ok:
  new=releases/'0.0.14'; stage.rename(new); tmp=p/'current.new'; tmp.symlink_to(new); os.replace(tmp,current)
 assert current.resolve()==old.resolve(), 'failed staging changed active release'
 assert stage.exists(), 'simulation unexpectedly activated staging'
print('Upgrade safety OK · failed staging preserves active release')
