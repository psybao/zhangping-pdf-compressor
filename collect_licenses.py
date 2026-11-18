import importlib.metadata as md
import json
from pathlib import Path
import shutil
ROOT=Path(__file__).parent
licenses=ROOT/'licenses';licenses.mkdir(exist_ok=True)
rows=[]
for dist in sorted(md.distributions(),key=lambda d:d.metadata['Name'].lower()):
    name=dist.metadata['Name'];version=dist.version
    license=dist.metadata.get('License-Expression') or dist.metadata.get('License') or '; '.join(dist.metadata.get_all('Classifier',[]))
    folder=licenses/(name+'-'+version);folder.mkdir(exist_ok=True)
    (folder/'METADATA.txt').write_text('\n'.join(f'{k}: {v}' for k,v in dist.metadata.items()),encoding='utf-8')
    for f in dist.files or []:
        if any(word in str(f).lower() for word in ['license','copying','notice']) and str(f).lower().endswith(('.txt','.md','license','copying','notice')):
            src=Path(dist.locate_file(f))
            if src.is_file():
                target=folder/str(f).replace('/','_').replace('\\','_');shutil.copyfile(src,target)
    rows.append({'name':name,'version':version,'license':license})
(ROOT/'output'/'python_components.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
for repo in ['pdf-diet','PdfBox-Android','pdf-tools']:
    folder=licenses/repo;folder.mkdir(exist_ok=True)
    for name in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md']:
        if (ROOT/'vendor'/repo/name).exists():shutil.copyfile(ROOT/'vendor'/repo/name,folder/name)
shutil.copyfile(ROOT/'assets'/'OFL.txt',licenses/'NotoSansCJK-OFL.txt')
print('License metadata and available license texts collected for',len(rows),'Python distributions')
