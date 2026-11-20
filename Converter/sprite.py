import struct,sys,os,zlib,collections

def load(p):
    return unwrap(open(p,'rb').read())

def unwrap(b):
    if len(b)>10 and b[8:10] in (b'\x78\xda',b'\x78\x9c',b'\x78\x01',b'\x78\x5e'):
        try:
            raw=struct.unpack('<I',b[4:8])[0]; d=zlib.decompress(b[8:])
            if len(d)==raw: return d
        except Exception: pass
    return b

def parse(b,start=0,with_end=False):
    nF,ver,nI,_=struct.unpack('<4i',b[start:start+16]); pos=start+16
    if ver!=2 or not(0<=nI<5000) or not(0<=nF<100000): raise ValueError('hdr')
    dims=[]
    for i in range(nI):
        dims.append(struct.unpack('<2i',b[pos:pos+8])); pos+=8
    frames=[]
    for i in range(nF):
        frames.append(struct.unpack('<12i',b[pos:pos+48])); pos+=48
    imgs=[]
    for i in range(nI):
        sz,=struct.unpack('<I',b[pos:pos+4]); pos+=4
        imgs.append(b[pos:pos+sz]); pos+=sz
    if with_end: return dims,frames,imgs,pos
    return dims,frames,imgs,len(b)-pos

def tokens(data,w,h,bpp):
    """yield (kind,n,pixelbytes) ; returns True if exactly consumed"""
    i=0;n=len(data);total=w*h;cnt=0
    out=[]
    while i<n and cnt<total:
        o=data[i];i+=1
        if o<0x40:
            out.append((0,o,data[i:i+bpp*o])); i+=bpp*o; cnt+=o
        elif o<0x80:
            out.append((1,o-0x40,data[i:i+bpp])); i+=bpp; cnt+=o-0x40
        else:
            out.append((2,o&0x3f,b'')); cnt+=o&0x3f
    return out,cnt==total and i==n

def to_rgba(px,bpp,fmt):
    if bpp==3: return bytes((px[2],px[1],px[0],255))
    v=px[0]|px[1]<<8
    if fmt=='565': return bytes(((v>>11&31)*255//31,(v>>5&63)*255//63,(v&31)*255//31,255))
    return bytes(((v>>10&31)*255//31,(v>>5&31)*255//31,(v&31)*255//31,255))

def find_bpp(data,w,h):
    for bpp in (3,2,4,1):
        try:
            t,ok=tokens(data,w,h,bpp)
            if ok: return bpp,t
        except Exception: pass
    return None,None

if __name__=='__main__':
    b=load(sys.argv[1]); d,f,im,rest=parse(b)
    print(d[:5],f[:3],[len(x) for x in im[:5]],'rest',rest)


def png_bytes(w,h,rgba):
    def chunk(t,d):
        c=struct.pack('>I',len(d))+t+d
        return c+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    raw=bytearray()
    stride=w*4
    for y in range(h):
        raw.append(0); raw+=rgba[y*stride:(y+1)*stride]
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))
            +chunk(b'IDAT',zlib.compress(bytes(raw),6))+chunk(b'IEND',b''))

def render(data,w,h,bpp,fmt='565'):
    toks,ok=tokens(data,w,h,bpp)
    out=bytearray(w*h*4); pos=0
    cache={}
    def conv(px):
        r=cache.get(px)
        if r is None:
            r=cache[px]=to_rgba(px,bpp,fmt)
        return r
    for kind,n,px in toks:
        if kind==0:
            for k in range(n):
                out[(pos+k)*4:(pos+k)*4+4]=conv(px[k*bpp:(k+1)*bpp])
        elif kind==1:
            c=conv(px); out[pos*4:(pos+n)*4]=c*n
        pos+=n
    return bytes(out)
