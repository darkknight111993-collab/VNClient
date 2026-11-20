import sys
sys.path.insert(0,r'c:\T3mpD3v0p5\Test\GitCode\Converter')
import sprite
b=sprite.load(sys.argv[1]); d,f,im,rest=sprite.parse(b)
print(b[:12].hex(' '),len(d),len(f),len(im),rest)
for x in d[:6]: print('dim',x)
for x in f[:8]: print('frm',x)
print([len(x) for x in im[:10]])
