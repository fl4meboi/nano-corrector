"""Explicit studio-background correction, separate from garment tonal matching."""
import argparse,json,sys,shutil
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nano_corrector import engine as E
from nano_corrector.background import fit_background,apply_background
from nano_corrector.cli import load_rgb,expand_inputs
ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
if args.out.exists():raise SystemExit('Choose a new output folder to preserve earlier versions')
paths=expand_inputs([str(args.source)]);ref=load_rgb(args.reference)[0];ref_anchor,ref_coeff,_=fit_background(ref);target=ref_anchor.lab
args.out.mkdir(parents=True)
rows=[]
for p in paths:
 rgb,alpha,icc=load_rgb(p);dest=args.out/(p.stem+'_wb.png');an,co,mask=fit_background(rgb)
 if p.resolve()==args.reference.resolve():
  out=rgb;clipped=0.;status='reference unchanged'
 else:out,clipped=apply_background(rgb,an.lab,co,target,ref_coeff);status='background matched'
 Image.fromarray(np.dstack([out,alpha]) if alpha is not None else out).save(dest,**({'icc_profile':icc} if icc else {}))
 check=np.asarray(Image.open(dest).convert('RGB'));assert check.shape==rgb.shape
 if status=='reference unchanged':assert np.array_equal(check,rgb)
 aft=E.find_neutral_anchor(check)
 row={'file':str(p),'output':str(dest),'status':status,'dimensions':list(Image.open(dest).size),'anchor_lab_before':an.lab.tolist(),'anchor_lab_after':aft.lab.tolist(),'coefficients_ab':co.tolist(),'gamut_limited_pct':clipped*100}
 rows.append(row);print(p.name, 'wall', np.round(an.lab,2), '->',np.round(aft.lab,2),'gamut limited %',round(clipped*100,4),flush=True)
report={'reference':str(args.reference),'target_lab':target.tolist(),'method':'Robust spatial wall tint fit, bright low-chroma feathering, median wall lightness match. Originals used; no garment tone correction.','images':rows}
(args.out/'report.json').write_text(json.dumps(report,indent=2))
