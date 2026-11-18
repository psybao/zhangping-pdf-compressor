"""Generate synthetic test PDFs locally; no user PDF is required or uploaded."""
from pathlib import Path
import shutil
from test_engine import fixtures, FIX

if __name__ == '__main__':
    fixtures()
    target=Path(__file__).parent/'android/app/src/androidTest/assets'
    target.mkdir(parents=True,exist_ok=True)
    for pdf in FIX.glob('*.pdf'):shutil.copyfile(pdf,target/pdf.name)
    print('Generated test PDFs and prepared Android instrumentation assets.')
