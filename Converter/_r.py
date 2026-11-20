import sys,os
sys.path.insert(0,r'c:\T3mpD3v0p5\Test\GitCode\Converter')
import sprite
p=sys.argv[1]; out=sys.argv[2]; k=int(sys.argv[3])
b=sprite.load(p); d,f,im,rest=sprite.parse(b)
h,w=d[k]
import struct
X=struct.unpack('<i',b[12:16])[0]
bpp=2 if X>1000 else 3
print(w,h,bpp,X)
for fmt in ('565','555'):
    open(f'{out}_{fmt}.png','wb').write(sprite.png_bytes(w,h,sprite.render(im[k],w,h,bpp,fmt)))
