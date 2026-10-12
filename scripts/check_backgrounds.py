from pathlib import Path
import json,sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np,cv2
from PIL import Image,ImageDraw
from nano_corrector import engine as E
ap=argparse.ArgumentParser();ap.add_argument('source',type=Path);ap.add_argument('output',type=Path);ap.add_argument('--qa',type=Path,required=True);args=ap.parse_args();src=args.source;dst=args.output;qa=args.qa;qa.mkdir(parents=True,exist_ok=True)
paths=sorted(src.glob('*'));rows=[]
sheet=Image.new('RGB',(1600,1140),'#222222');sd=ImageDraw.Draw(sheet)
allsh=Image.new('RGB',(1536,1504),'#222222');ad=ImageDraw.Draw(allsh)
for i,p in enumerate(paths):
 orig=np.asarray(Image.open(p).convert('RGB'));out=np.asarray(Image.open(dst/(p.stem+'_wb.png')).convert('RGB'));h,w=orig.shape[:2]
 row={'image':p.name,'patches':{}}
 for name,(x,y) in {'upper_left':(.05,.1),'upper_right':(.9,.1),'middle_left':(.05,.45),'middle_right':(.9,.45)}.items():
  vals=[]
  for im in [orig,out]:
   crop=im[int(h*y):int(h*(y+.06)),int(w*x):int(w*(x+.04))]
   rgb=np.median(crop.reshape(-1,3),axis=0)
   lab=cv2.cvtColor((rgb/255).astype(np.float32).reshape(1,1,3),cv2.COLOR_RGB2Lab).reshape(3)
   vals.append({'rgb':rgb.tolist(),'lab':lab.tolist()})
  row['patches'][name]={'before':vals[0],'after':vals[1]}
 rows.append(row)
 for j,im in enumerate([orig,out]):
  t=Image.fromarray(im);t.thumbnail((252,340));x=(i%3)*512+j*256;y=(i//3)*376;allsh.paste(t,(x,y+28));ad.text((x+5,y+8),p.stem+(' BEFORE' if j==0 else ' AFTER'),fill='white')
  if i>=8:
   t=Image.fromarray(im);t.thumbnail((400,536));sheet.paste(t,((i-8)*400,j*570+30));sd.text(((i-8)*400+5,j*570+8),p.stem+(' BEFORE' if j==0 else ' AFTER'),fill='white')
 if i in [1,8,9,10]:
  # Actual wall pixels, nearest-neighbor enlargement, no tint normalization.
  crop=Image.new('RGB',(800,440),'#222222');cd=ImageDraw.Draw(crop)
  for j,im in enumerate([orig,out]):
   t=Image.fromarray(im[int(h*.12):int(h*.32),int(w*.03):int(w*.19)]);t=t.resize((400,400))
   crop.paste(t,(j*400,30));cd.text((j*400+6,8),p.stem+(' BEFORE' if j==0 else ' AFTER'),fill='white')
  crop.save(qa/(p.stem+'-wall.jpg'),quality=98)
summary={}
for subset,indices in [('IJKL',range(8,12)),('all',range(12))]:
 summary[subset]={}
 for name in rows[0]['patches']:
  result={}
  for when in ['before','after']:
   vv=[np.array(rows[i]['patches'][name][when]['lab']) for i in indices]
   ref=np.array(rows[11]['patches'][name]['before']['lab'])
   result[when+'_mean_tint_distance_to_L']=float(np.mean([np.linalg.norm(v[1:]-ref[1:]) for v in vv]))
   result[when+'_max_pairwise_tint_spread']=float(max(np.linalg.norm(a[1:]-b[1:]) for a in vv for b in vv))
  summary[subset][name]=result
sheet.save(qa/'IJKL-before-after.jpg',quality=97);allsh.save(qa/'all-before-after.jpg',quality=96)
(qa/'background-check.json').write_text(json.dumps({'summary':summary,'images':rows},indent=2))
print(json.dumps(summary,indent=2))
