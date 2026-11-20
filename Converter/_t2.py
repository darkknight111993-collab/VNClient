import sys,os,random,collections,struct
sys.path.insert(0,r'c:\T3mpD3v0p5\Test\GitCode\Converter')
import sprite
R=r'c:\T3mpD3v0p5\Test\GitCode\ExtractedAssets'
files=[]
for a in ('fx','charte','emote','fxasset'):
    for r,_,fs in os.walk(os.path.join(R,a)):
        for f in fs:
            if f!='manifest.json': files.append(os.path.join(r,f))
random.seed(2); random.shuffle(files)
st=collections.Counter(); ex={}
for p in files[:int(sys.argv[1])]:
    try:
        b=sprite.load(p); d,f,im,rest=sprite.parse(b)
    except Exception as e: continue
    X=struct.unpack('<i',b[12:16])[0]
    for k,((hh,ww),data) in enumerate(zip(d,im)):
        if hh*ww==0: continue
        ok=tuple(bpp for bpp in (1,2,3,4) if sprite.tokens(data,ww,hh,bpp)[1])
        fl=sorted(set(fr[2] for fr in f if fr[3]==k))
        key=(X,tuple(fl)[:2],ok); st[key]+=1; ex.setdefault(key,p)
for k,v in sorted(st.items(),key=lambda x:-x[1])[:40]: print(k,v,os.path.basename(ex[k]))
