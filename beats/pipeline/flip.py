#!/usr/bin/env python3
"""After You've Gone -> Kanye-style summer-soul flip.
Vocal-forward (Gold Digger / Good Life / Famous lane): isolated vocal chop,
brass tamed to a single homage stab, bright punchy drums + in-key 808.
"""
import numpy as np, librosa, soundfile as sf
from scipy.signal import butter, sosfilt
np.random.seed(21)
SR=44100
BASE="/home/user/Shorts-pipeline/beats"
STEM=f"{BASE}/stems/htdemucs/After_Youve_Gone"

# ---------------- params ----------------
CHOP_START=96.14      # downbeat of the sung climax
NBARS=4
SEMIS=6               # +6 -> bright shimmer, drums ~83 BPM
ORIG_BPM=117.454
BAR=60/ORIG_BPM*4

def hp(x,f,o=2): return sosfilt(butter(o,f/(SR/2),'hp',output='sos'),x)
def lp(x,f,o=4): return sosfilt(butter(o,f/(SR/2),'lp',output='sos'),x)
def bp(x,lo,hi): return sosfilt(butter(2,[lo/(SR/2),hi/(SR/2)],'bp',output='sos'),x)
def stereo(fn,x,*a): return np.stack([fn(x[c],*a) for c in range(2)])

def load(name):
    y,_=librosa.load(f"{STEM}/{name}.mp3",sr=SR,mono=False)
    return y if y.ndim==2 else np.stack([y,y])

# ---------------- chop the isolated vocal ----------------
voc=load("vocals")
ratio=2**(SEMIS/12)
def speedup(seg):
    return np.stack([librosa.resample(seg[c],orig_sr=SR,target_sr=int(SR/ratio)) for c in range(2)])
vseg=voc[:, int(CHOP_START*SR):int((CHOP_START+NBARS*BAR)*SR)].copy()
chop=speedup(vseg)
DRUM_BPM=ORIG_BPM*ratio/2
BEAT=60/DRUM_BPM; BARL=BEAT*4
# warm/bright vocal EQ: clear mud, gentle air, no harsh mids
chop=stereo(hp,chop,150)
chop=stereo(lp,chop,12500)
# seamless loop
n=int(0.05*SR); fi=np.linspace(0,1,n)
chop[:, :n]=chop[:, -n:]*fi[::-1]+chop[:, :n]*fi
chop=chop/np.max(np.abs(chop))*0.9
LOOPN=chop.shape[1]
BARS_IN_LOOP=int(round(LOOPN/(BARL*SR)))

# ---------------- homage brass stab (from 'other', tamed) ----------------
oth=load("other")
# grab a punchy slice, speed-match, gate it SHORT so it's a stab not a wash
ostab=speedup(oth[:, int((CHOP_START)*SR):int((CHOP_START+0.55*BAR)*SR)].copy())
slen=int(0.34*SR); ostab=ostab[:, :slen]
g=np.ones(slen); a=int(0.006*SR); d=int(0.18*SR)
g[:a]=np.linspace(0,1,a); g[-d:]*=np.linspace(1,0,d)
ostab=ostab*g
ostab=stereo(bp,ostab,500,4500)          # brass-ish band only
ostab=ostab/ (np.max(np.abs(ostab))+1e-9) *0.5

# ---------------- drum kit (bright, summery, punchy) ----------------
def kick():
    n=int(0.28*SR); t=np.arange(n)/SR
    f=125*np.exp(-t*26)+55
    s=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*8)
    s+=np.sin(2*np.pi*2600*t)*np.exp(-t*200)*0.4
    return np.tanh(s*1.2)*0.9
def clap():
    n=int(0.22*SR); t=np.arange(n)/SR
    bursts=np.zeros(n)
    for o in [0,0.008,0.016]:
        i=int(o*SR); bursts[i:]+=np.random.randn(n-i)*np.exp(-np.arange(n-i)/SR*45)
    bursts+=np.random.randn(n)*np.exp(-t*12)*0.6
    return hp(bursts,1200)*0.55
def snare():
    n=int(0.2*SR); t=np.arange(n)/SR
    s=hp(np.random.randn(n),1800)*np.exp(-t*22)*0.8
    s+=(np.sin(2*np.pi*200*t))*np.exp(-t*26)*0.4
    return s*0.7
def hat(o=False):
    n=int((0.1 if o else 0.035)*SR); t=np.arange(n)/SR
    return hp(np.random.randn(n),9000,4)*np.exp(-t*(40 if o else 130))*(0.42 if o else 0.32)
def shaker():
    n=int(0.06*SR); t=np.arange(n)/SR
    return bp(np.random.randn(n),5000,11000)*np.exp(-t*60)*0.25
def tamb():
    n=int(0.09*SR); t=np.arange(n)/SR
    return hp(np.random.randn(n),6000,4)*np.exp(-t*55)*0.3
K,CL,S,Hc,Ho,SH,TM=kick(),clap(),snare(),hat(),hat(True),shaker(),tamb()

def mono_track(N):
    return np.zeros(N)
def place(tr,snd,t,g=1.0):
    i=int(t*SR); 
    if i>=tr.shape[0]: return
    m=min(snd.shape[0],tr.shape[0]-i); tr[i:i+m]+=snd[:m]*g

N=LOOPN
drums=mono_track(N); kenv=mono_track(N)
for b in range(BARS_IN_LOOP):
    b0=b*BARL
    # kick: 1, & of 2, syncopated push -> driving but breathing
    for kt,kg in [(0,1.0),(0.75*BEAT,0.5),(2.5*BEAT,0.85)]:
        place(drums,K,b0+kt,kg); place(kenv,np.ones(int(0.001*SR)),b0+kt)
    # backbeat: snare + clap layered on 2 & 4 (bright snap)
    for st in [1,3]:
        place(drums,S,b0+st*BEAT,0.9); place(drums,CL,b0+st*BEAT,1.0)
    # crisp hats 8ths + shaker offbeats + tambourine on the & of 4
    for j in range(8):
        t=b0+j*(BEAT/2)+(0.008 if j%2 else 0)
        place(drums, Ho if j==7 else Hc, t, 0.5 if j==7 else 0.34*(0.85+0.3*np.random.rand()))
        if j%2: place(drums,SH,t,0.8)
    place(drums,TM,b0+3.5*BEAT,0.7)
drums=np.stack([drums,drums])

# sidechain pump (clean low end + space)
sc=np.ones(N)
for i in np.where(kenv>0)[0]:
    dur=int(0.16*SR); seg=np.linspace(0.5,1,dur); e=min(dur,N-i)
    sc[i:i+e]=np.minimum(sc[i:i+e],seg[:e])
sc=np.stack([sc,sc])

# ---------------- 808 / sub in D (key) ----------------
D2=73.42
sub=mono_track(N)
def sub_note(freq,t0,dur,glide=None):
    n=int(dur*SR); t=np.arange(n)/SR
    f=np.full(n,freq)
    if glide: f=np.linspace(glide,freq,n)
    s=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*1.2)
    s=np.tanh(s*1.6)*0.5
    place(sub,s,t0)
for b in range(BARS_IN_LOOP):
    b0=b*BARL
    sub_note(D2,b0+0,BEAT*2.3)
    sub_note(D2*2**(-2/12),b0+2.5*BEAT,BEAT*1.4,glide=D2)   # little movement (C#/D)
    sub_note(D2*2**(3/12),b0+3.5*BEAT,BEAT*0.6)             # F lift
sub=np.stack([sub,sub])

# ---------------- arrange (room for a rapper) ----------------
def blocks():
    return [
      dict(kind="intro", samp=1.0, dr=0.0, bs=0.0, stab=True,  filt=1500),
      dict(kind="verse", samp=1.0, dr=1.0, bs=1.0, stab=True,  filt=None),
      dict(kind="verse", samp=1.0, dr=1.0, bs=1.0, stab=False, filt=None),
      dict(kind="lift",  samp=1.0, dr=1.0, bs=1.0, stab=True,  filt=None),
      dict(kind="verse", samp=1.0, dr=1.0, bs=1.0, stab=False, filt=None),
      dict(kind="break", samp=0.9, dr=0.0, bs=0.7, stab=True,  filt=1100),
      dict(kind="verse", samp=1.0, dr=1.0, bs=1.0, stab=True,  filt=None),
      dict(kind="outro", samp=1.0, dr=0.5, bs=0.4, stab=False, filt=1600),
    ]
pieces=[]
for blk in blocks():
    s=chop.copy()
    if blk["filt"]: s=stereo(lp,s,blk["filt"])*1.12
    d=drums*blk["dr"]; bs=sub*blk["bs"]
    if blk["dr"]>0:
        s=s*(0.6+0.4*sc); bs=bs*sc
    # homage brass stab: ONE hit per 2 bars on beat 1 (tamed)
    stabtr=np.zeros((2,N))
    if blk["stab"]:
        for b in range(0,BARS_IN_LOOP,2):
            i=int(b*BARL*SR); m=min(ostab.shape[1],N-i)
            if i<N: stabtr[:, i:i+m]+=ostab[:, :m]
        if blk["dr"]>0: stabtr=stabtr*(0.6+0.4*sc)
    mix=s*0.95 + d + bs + stabtr*0.55
    pieces.append(mix)
out=np.concatenate(pieces,axis=1)

# ---------------- master (warm + bright + loud) ----------------
out=np.stack([hp(out[c],35) for c in range(2)])      # clean dc/rumble
# gentle high-shelf air
air=np.stack([hp(out[c],8000,2) for c in range(2)])*0.12
out=out+air
out=np.tanh(out*1.18)
out=out/np.max(np.abs(out))*0.97
fi=int(0.05*SR); fo=int(1.0*SR)
out[:, :fi]*=np.linspace(0,1,fi); out[:, -fo:]*=np.linspace(1,0,fo)
sf.write(f"{BASE}/renders/flip_v3.wav",out.T,SR)
print(f"v3 rendered: {DRUM_BPM:.1f} BPM, +{SEMIS} semis, loop {LOOPN/SR:.2f}s "
      f"({BARS_IN_LOOP} bars), total {out.shape[1]/SR:.1f}s")
