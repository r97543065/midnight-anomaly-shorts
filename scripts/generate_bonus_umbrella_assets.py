from PIL import Image, ImageDraw, ImageFilter, ImageFont
import random, math, json, os, hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'assets/episodes/20261031-umbrella-bonus';D.mkdir(parents=True,exist_ok=True)
W,H=720,1280
INK=(9,18,25); GOLD=(223,176,100); BLUE=(58,143,161); RAIN=(108,180,200)

def base(seed, warm_x=550, warm_y=290):
    rnd=random.Random(seed)
    ys=np.arange(H,dtype=np.float32)[:,None]; xs=np.arange(W,dtype=np.float32)[None,:]
    v=np.clip(.52-(ys/H)*.25 + .10*np.cos((xs-W*.55)*.007),.05,.7)
    light=np.exp(-((xs-warm_x)**2/155000+(ys-warm_y)**2/220000))*0.23
    arr=np.empty((H,W,3),dtype=np.uint8)
    for k,c in enumerate((12,29,39)):
      arr[:,:,k]=np.clip(c+v*(16+k*5)+light*(180 if k==0 else 124 if k==1 else 52),0,255)
    im=Image.fromarray(arr,'RGB')
    d=ImageDraw.Draw(im,'RGBA')
    d.polygon([(0,340),(240,420),(240,825),(0,1130)],fill=(6,16,23,244))
    d.polygon([(W,360),(490,430),(490,850),(W,1170)],fill=(3,12,20,245))
    d.polygon([(240,825),(490,850),(W,H),(0,H)],fill=(11,26,32,247))
    d.line([(0,340),(240,420),(490,430),(W,360)],fill=(102,151,155,70),width=4)
    for j in range(11):
      y=850+int((j/11)**1.3*410)
      d.line((int(240-240*(y-850)/430),y,int(490+230*(y-850)/430),y),fill=(100,145,152,int(13+j*2)),width=2)
    d.rectangle((250,390,488,832),fill=(3,11,17,245),outline=(65,110,126,165),width=4)
    d.ellipse((292,420,440,490),fill=(80,143,145,21))
    for i in range(100):
      x=rnd.randint(0,W);y=rnd.randint(0,H)
      d.line((x,y,x+rnd.randint(-10,10),y+rnd.randint(15,62)),fill=(160,204,211,rnd.randint(2,18)),width=1)
    return im

def glow(im,xy,r,color=(90,174,192),alpha=95):
    layer=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(layer,'RGBA')
    for k in range(10,0,-1):
      rad=int(r*k/10); op=int(alpha*(11-k)/80)
      d.ellipse((xy[0]-rad,xy[1]-rad,xy[0]+rad,xy[1]+rad),fill=(*color,op))
    layer=layer.filter(ImageFilter.GaussianBlur(40));im.paste(layer,(0,0),layer)

def umbrella(d,cx,cy,s=1.0,angle=0):
    # Canopy centered at (cx, cy); shaft downwards
    half=int(172*s);top=int(120*s); bot=int(55*s)
    poly=[(cx-half,cy+bot),(cx-int(154*s),cy-int(4*s)),(cx-int(113*s),cy-int(76*s)),(cx-int(45*s),cy-int(111*s)),(cx,cy-int(122*s)),(cx+int(55*s),cy-int(108*s)),(cx+int(132*s),cy-int(55*s)),(cx+half,cy+bot), (cx+int(122*s),cy+int(28*s)),(cx+int(54*s),cy+int(46*s)),(cx,cy+int(34*s)),(cx-int(67*s),cy+int(49*s)),(cx-int(124*s),cy+int(26*s))]
    d.polygon(poly,fill=(5,10,14,255),outline=(91,131,136,230),width=max(2,int(3*s)))
    for dest in (cx-half,cx-int(66*s),cx,cx+int(58*s),cx+half):
      d.line((cx,cy-int(122*s),dest,cy+int(42*s)),fill=(116,163,168,150),width=max(1,int(2*s)))
    d.line((cx,cy+int(38*s),cx,cy+int(440*s)),fill=(114,139,143,245),width=max(2,int(7*s)))
    d.arc((cx-int(43*s),cy+int(395*s),cx+int(43*s),cy+int(488*s)),start=8,end=190,fill=(119,147,152,255),width=max(2,int(6*s)))

def figure(d,cx,cy,s=1,shade=(3,10,14,255),eyes=False):
    head=int(52*s);h=int(340*s);body=int(80*s)
    d.ellipse((cx-head,cy-head,cx+head,cy+head),fill=shade)
    d.polygon([(cx-head,cy+45*s),(cx+head,cy+45*s),(cx+body,cy+h),(cx-body,cy+h)],fill=shade)
    d.line((cx-int(54*s),cy+int(190*s),cx-int(81*s),cy+int(365*s)),fill=shade,width=max(4,int(33*s)))
    d.line((cx+int(52*s),cy+int(190*s),cx+int(81*s),cy+int(365*s)),fill=shade,width=max(4,int(33*s)))
    if eyes:
      d.ellipse((cx-int(30*s),cy-int(10*s),cx-int(17*s),cy-int(1*s)),fill=(213,223,217,200))
      d.ellipse((cx+int(17*s),cy-int(10*s),cx+int(30*s),cy-int(1*s)),fill=(213,223,217,200))

def droplets(d,cx,cy,n,rnd,up=True):
    for i in range(n):
      x=cx+rnd.randint(-135,135); y=cy+rnd.randint(-260,390)
      sz=rnd.randint(2,8)
      d.ellipse((x-sz//2,y-sz,x+sz//2,y+sz),fill=(123,203,221,rnd.randint(95,225)))
      if up:d.line((x,y+sz,x+rnd.randint(-2,2),y+sz+rnd.randint(20,70)),fill=(87,175,199,70),width=2)

def shoes(d,x,y,s=1,light=False):
    for dx in (-39,39):
      box=(int(x+(dx-23)*s),int(y-74*s),int(x+(dx+23)*s),int(y+75*s))
      d.rounded_rectangle(box,radius=int(18*s),fill=((60,87,92,255) if light else (5,9,12,255)),outline=(120,156,158,170),width=3)
      for k in range(3):
        d.line((box[0]+8,box[1]+20+k*15,box[2]-8,box[1]+19+k*15),fill=(150,160,158,110),width=2)

def puddle(d,x,y,scale):
    for z in range(7):
      rx=int(scale*(1-z*.10));ry=int(scale*.32*(1-z*.12));
      d.ellipse((x-rx,y-ry,x+rx,y+ry),outline=(75,160,179,int(30+z*13)),width=2)

def final_art(i):
    rnd=random.Random(314159+i*317);im=base(i,warm_x=[560,460,565,480,400,230,490,470][i],warm_y=[350,180,330,390,520,480,360,500][i]);d=ImageDraw.Draw(im,'RGBA')
    if i==0:
      # Black umbrella in foyer, water rising
      glow(im,(389,675),220)
      d=ImageDraw.Draw(im,'RGBA');umbrella(d,364,605,.94)
      droplets(d,365,620,80,rnd)
      d.line((175,1060,600,1060),fill=(110,151,146,120),width=4)
    if i==1:
      # Ceiling flooded from below
      glow(im,(355,325),360)
      d=ImageDraw.Draw(im,'RGBA');
      for radius in range(13):
        d.arc((120+radius*8,45+radius*10,620-radius*8,540-radius*11),5,178,fill=(83,171,196,40+radius*9),width=3)
      droplets(d,347,465,45,rnd)
      d.ellipse((145,55,596,410),outline=(100,172,192,145),width=6)
    if i==2:
      # Camera look, umbrella casts extra person's shadow
      glow(im,(487,565),300);d=ImageDraw.Draw(im,'RGBA')
      d.polygon([(100,610),(395,440),(628,940),(275,1130)],fill=(4,11,16,150))
      figure(d,478,570,.65,(5,12,16,180));figure(d,570,545,.56,(3,8,10,160))
      umbrella(d,345,690,.55)
      for xy in [(64,130),(98,130),(132,130)]:d.ellipse((xy[0]-6,xy[1]-6,xy[0]+6,xy[1]+6),fill=(193,59,56,205))
      d.line((36,110,684,110),fill=(90,170,185,100),width=3)
    if i==3:
      # umbrella underside + ghost receipt
      d=ImageDraw.Draw(im,'RGBA');umbrella(d,360,500,1.75)
      d.polygon([(294,585),(483,558),(503,900),(309,922)],fill=(190,181,151,240))
      d.line((319,650,462,631),fill=(74,66,59,225),width=5)
      d.line((324,680,452,667),fill=(74,66,59,150),width=4)
      d.line((327,712,465,694),fill=(74,66,59,120),width=4)
      glow(im,(348,650),135,(189,174,117),50)
    if i==4:
      # approaching footprints / puddle in the corridor
      d=ImageDraw.Draw(im,'RGBA');puddle(d,365,982,285)
      for k in range(7):
        y=515+k*92;sc=.4+k*.095;x=355+(-1)**k*40
        d.ellipse((x-16*sc,y-33*sc,x+16*sc,y+34*sc),fill=(64,153,174,110+k*12))
      d.line((100,1120,620,1120),fill=(83,171,185,140),width=3)
      droplets(d,355,490,20,rnd)
    if i==5:
      # doorway full of rain, umbrella double
      glow(im,(350,510),370,(93,159,204),130);d=ImageDraw.Draw(im,'RGBA')
      d.rectangle((180,260,551,1060),fill=(10,39,53,255),outline=(130,192,208,200),width=10)
      for k in range(220):
        x=rnd.randint(192,540);y=rnd.randint(265,1050)
        d.line((x,y,x-rnd.randint(2,18),y+rnd.randint(24,93)),fill=(139,207,218,rnd.randint(40,140)),width=2)
      figure(d,367,565,1.03,eyes=False)
      umbrella(d,380,475,1.22)
    if i==6:
      # doubles face; one shadow black and one light reflecting
      glow(im,(400,500),350,(147,185,196),75);d=ImageDraw.Draw(im,'RGBA')
      figure(d,365,590,1.45,(5,13,17,250),eyes=True)
      d.arc((309,560,419,655),12,166,fill=(176,153,150,120),width=3)
      umbrella(d,440,870,.85)
      droplets(d,447,830,25,rnd)
    if i==7:
      # two pairs of shoes, thrown umbrella by threshold
      glow(im,(450,850),300,(127,175,193),78);d=ImageDraw.Draw(im,'RGBA')
      d.polygon([(195,790),(545,790),(690,1220),(50,1220)],fill=(7,22,28,180))
      shoes(d,290,1010,1.00);shoes(d,470,1050,1.0,True)
      d.line((112,1140,580,620),fill=(125,149,145,200),width=8)
      d.pieslice((454,480,704,710),180,360,fill=(4,10,15,235),outline=(101,142,154,220),width=4)
      puddle(d,510,1200,155)
    # cinematic grain & vignette
    a=np.asarray(im).copy().astype(np.int16)
    nr=np.random.default_rng(i*857+2002)
    noise=nr.normal(0,2.15,(H,W,1))
    yy,xx=np.ogrid[0:H,0:W];vg=(1-0.34*(((xx-W/2)/(W/2))**2+((yy-H/2)/(H/2))**2))
    a=np.clip((a+noise)*vg[:,:,None],0,255).astype(np.uint8)
    im=Image.fromarray(a,'RGB').resize((1080,1920),Image.Resampling.LANCZOS)
    p=D/f'scene{i+1:02d}.webp';im.save(p,'WEBP',quality=90,method=6)
    with Image.open(p) as check:
       assert check.format=='WEBP' and check.size==(1080,1920) and check.n_frames==1; check.load()
    return {'path':str(p),'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

if __name__=='__main__':
    data=[final_art(i) for i in range(8)];print(json.dumps(data,ensure_ascii=False,indent=2));
    # contact sheet review only (not a video scene!)
    sheet=Image.new('RGB',(4*270,2*480),(5,8,12))
    for i,o in enumerate(data):
      im=Image.open(o['path']);sheet.paste(im.resize((270,480),Image.Resampling.LANCZOS),((i%4)*270,(i//4)*480))
    out=ROOT/'output';out.mkdir(parents=True,exist_ok=True)
    sheet.save(out/'bonus-umbrella-contact-sheet.jpg',quality=90)