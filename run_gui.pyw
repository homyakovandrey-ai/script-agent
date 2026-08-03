import sys
import traceback
from pathlib import Path

log_path = Path(__file__).parent / "error.log"

try:
    # Ensure working directory is the script folder
    import os
    os.chdir(Path(__file__).parent)

    import app
    app.App().mainloop()

except Exception:
    log_path.write_text(traceback.format_exc(), encoding="utf-8")
