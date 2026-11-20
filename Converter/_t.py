import sys,os,random,collections,struct
sys.path.insert(0,r'c:\T3mpD3v0p5\Test\GitCode\Converter')
import sprite
R=r'c:\T3mpD3v0p5\Test\GitCode\ExtractedAssets'
files=[]
for a in ('fx','charte','emote','fxasset'):
    for r,_,fs in os.walk(os.path.join(R,a)):
        for f in fs:
            if f!='manifest.json': files.append(os.path.join(r,f))
random.seed(1); random.shuffle(files)
ok=bad=skip=0; st=collections.Counter(); errs=[]
for p in files[:int(sys.argv[1])]:
    try:
        b=sprite.load(p); d,f,im,rest=sprite.parse(b)
    except Exception as e:
        skip+=1; continue
    good=rest==0
    if rest: errs.append((p,'rest',rest))
    flag={}
    for fr in f: flag.setdefault(fr[3],fr[2])
    for k,((hh,ww),data) in enumerate(zip(d,im)):
        if hh*ww==0: continue
        bpp,t=sprite.find_bpp(data,ww,hh)
        st[(flag.get(k),bpp)]+=1
        if bpp is None: good=False; errs.append((p,k,ww,hh,len(data)))
    if good: ok+=1
    else: bad+=1
print(ok,bad,skip); print(sorted(st.items(),key=lambda x:-x[1])[:30])
for e in errs[:15]: print(e)
