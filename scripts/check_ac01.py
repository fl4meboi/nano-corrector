"""Reproducible AC-01 QA; fixed masks from originals, metrics never used to fit curves."""
from pathlib import Path
import argparse,json,sys
import numpy as np,cv2
from PIL import Image,ImageDraw
from scipy import ndimage as ndi
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from nano_corrector import engine as E
ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--qa',type=Path,required=True);args=ap.parse_args();args.qa.mkdir(parents=True,exist_ok=True)
files=sorted(p for p in args.source.iterdir() if p.suffix.lower() in ['.png','.jpg'])
sheet=Image.new('RGB',(1536,4*376),'#222222');draw=ImageDraw.Draw(sheet)
heat=Image.new('RGB',(1280,3*446),'#222222');hd=ImageDraw.Draw(heat)
rows=[];heatrow=0
for i,p in enumerate(files):
 dst=args.output/(p.stem+'_wb.png')
 with Image.open(p) as im: orig=np.array(im.convert('RGB'));size=im.size
 with Image.open(dst) as im: out=np.array(im.convert('RGB'));outsize=im.size
 assert orig.shape==out.shape,(p,size,outsize)
 ref=p.stem in ['AC01-A','AC01-L'];identical=bool(np.array_equal(orig,out))
 if ref:assert identical
 h,w=orig.shape[:2];smallsize=(round(w*800/max(h,w)),round(h*800/max(h,w)))
 old=cv2.resize(orig,smallsize,interpolation=cv2.INTER_AREA);new=cv2.resize(out,smallsize,interpolation=cv2.INTER_AREA)
 labs=[cv2.cvtColor(x.astype(np.float32)/255,cv2.COLOR_RGB2Lab) for x in [old,new]]
 L,a,b=labs[0].transpose(2,0,1);C=np.hypot(a,b);g=ndi.uniform_filter(np.hypot(ndi.sobel(L,0),ndi.sobel(L,1)),7)
 masks={'trousers':ndi.binary_opening((L>72)&(g<4)&(b>5)&(b<18)&(C>6)&(C<26)&(a<9),iterations=3),'hat':ndi.binary_erosion((a>40)&(L>25)&(L<60),iterations=2)}
 row={'image':p.name,'size':size,'reference':ref,'pixels_identical':identical,'objects':{}}
 for name,m in masks.items():
  if m.sum()>300:row['objects'][name]={'pixels':int(m.sum()),'before_lab':np.median(labs[0][m],axis=0).tolist(),'after_lab':np.median(labs[1][m],axis=0).tolist()}
 row['wall_before_lab']=E.find_neutral_anchor(orig).lab.tolist();row['wall_after_lab']=E.find_neutral_anchor(out).lab.tolist()
 bright=(E.srgb_to_linear(old.astype(np.float32)/255)@np.array([.2126,.7152,.0722]))>=((78+16)/116)**3
 row['bright_pixel_mean_absolute_change_u8']=float(np.abs(new.astype(float)-old)[bright].mean())
 rows.append(row)
 x=i%3*512;y=i//3*376
 for j,im in enumerate([old,new]):
  t=Image.fromarray(im);t.thumbnail((252,340));sheet.paste(t,(x+j*256,y+28));draw.text((x+j*256+6,y+7),p.stem+(' BEFORE' if j==0 else ' AFTER'),fill='white')
 if p.stem in ['AC01-A','AC01-B','AC01-K']:
  for j,im in enumerate([old,new]):
   t=Image.fromarray(im);t.thumbnail((320,410));heat.paste(t,(j*640,heatrow*446+28))
   # a*: green (-12) -> gray (0) -> magenta (+12), same scale for every panel.
   aa=np.clip(labs[j][...,1]/12,-1,1);col=np.empty((*aa.shape,3),np.uint8)
   col[...,0]=np.rint(128+127*aa);col[...,1]=np.rint(128-127*aa);col[...,2]=np.rint(128+127*aa)
   t=Image.fromarray(col);t.thumbnail((320,410));heat.paste(t,(j*640+320,heatrow*446+28))
   hd.text((j*640+6,heatrow*446+6),p.stem+(' BEFORE' if j==0 else ' AFTER')+' | a*: -12 green / +12 magenta',fill='white')
  heatrow+=1
 if p.stem in ['AC01-B','AC01-G','AC01-K']:
  comp=Image.new('RGB',(old.shape[1]*2,830),'#222222');d=ImageDraw.Draw(comp)
  for j,im in enumerate([old,new]):comp.paste(Image.fromarray(im),(j*old.shape[1],30));d.text((j*old.shape[1]+8,8),'BEFORE' if j==0 else 'AFTER',fill='white')
  comp.save(args.qa/(p.stem+'-comparison.jpg'),quality=96)
summary={}
for obj in ['trousers','hat']:
 rr=[r['objects'][obj] for r in rows if obj in r['objects']]
 stats={}
 for when in ['before','after']:
  v=[np.array(r[when+'_lab'][1:]) for r in rr];stats[when+'_max_pairwise_ab']=float(max(np.linalg.norm(a-b) for a in v for b in v))
 summary[obj]={'images':len(rr),**stats}
summary['dimensions_preserved']=True;summary['references_pixel_identical']=True
summary['limitations']='Object masks are color-threshold proxies, not semantic segmentation. Cross-pose color spread is a consistency check, not proof of true color accuracy. Trouser mask overlaps the low-chroma fit population; saturated hat is excluded from fitting.'
report={'summary':summary,'images':rows};(args.qa/'sanity-check.json').write_text(json.dumps(report,indent=2));sheet.save(args.qa/'before-after.jpg',quality=95);heat.save(args.qa/'magenta-heatmap.jpg',quality=95)
print(json.dumps(summary,indent=2))
