import sys
sys.path.insert(0,r'c:\T3mpD3v0p5\Test\GitCode\Converter')
import sprite
b=sprite.load(sys.argv[1]); d,f,im,rest=sprite.parse(b)
k=int(sys.argv[2])
print(d[k],len(im[k]))
data=im[k]
for i in range(0,min(len(data),int(sys.argv[3])),32): print('%04x'%i,data[i:i+32].hex(' '))
