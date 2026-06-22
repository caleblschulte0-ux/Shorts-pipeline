#!/usr/bin/env python3
"""After You've Gone -> summer-soul flip v4.
Real CC0 drum one-shots + pedalboard mixing/FX. Tasteful, targeted saturation.
Vocal-forward (Gold Digger / Good Life lane), brass tamed to a homage stab.
"""
import numpy as np, librosa, soundfile as sf, glob, os
from pedalboard import (Pedalboard, Compressor, Gain, Reverb, Distortion,
                        Limiter, HighShelfFilter, LowShelfFilter, PeakFilter,
                        HighpassFilter, LowpassFilter)
np.random.seed(21)
SR=44100
BASE="/home/user/Shorts-pipeline/beats"
KIT=f"{BASE}/kit/soulful-vintage"
# prefer fine-tuned wav stems, fall back to mp3 stems
VWAV=f"{BASE}/stems_wav/htdemucs_ft/After_Youve_Gone"
VMP3=f"{BASE}/stems/htdemucs/After_Youve_Gone"
STEM = VWAV if os.path.exists(f"{VWAV}/vocals.wav") else VMP3
VEXT = "wav" if STEM==VWAV else "mp3"

CHOP_START=96.14; NBARS=4; SEMIS=6
ORIG_BPM=117.454; BAR=60/ORIG_BPM*4

# ---- io helpers ----
def load_stem(name):
    y,_=librosa.load(f"{STEM}/{name}.{VEXT}",sr=SR,mono=False)
    return y if y.ndim==2 else np.stack([y,y])
def load_oneshot(path):
    y,_=librosa.load(path,sr=SR,mono=True)
    return np.stack([y,y]).astype(np.float32)
def find(sub,*names):
    for n in names:
        g=glob.glob(f"{KIT}/{sub}/*{n}*")
        if g: return g[0]
    return glob.glob(f"{KIT}/{sub}/*")[0]

def fx(board,x):   # apply a Pedalboard to (2,N) float32
    return board(x.astype(np.float32),SR)
def saturate(x,drive_db,mix):  # parallel, tasteful saturation
    wet=Pedalboard([Distortion(drive_db=drive_db)])(x.astype(np.float32),SR)
    m=max(np.max(np.abs(x)),1e-9); wm=max(np.max(np.abs(wet)),1e-9)
    wet=wet*(m/wm)              # level-match so 'mix' is real blend, not louder
    return (x*(1-mix)+wet*mix).astype(np.float32)

ratio=2**(SEMIS/12)
def speedup(seg):
    return np.stack([librosa.resample(seg[c],orig_sr=SR,target_sr=int(SR/ratio)) for c in range(2)])

# ================= SAMPLE: isolated vocal chop =================
voc=load_stem("vocals")
chop=speedup(voc[:, int(CHOP_START*SR):int((CHOP_START+NBARS*BAR)*SR)].copy())
DRUM_BPM=ORIG_BPM*ratio/2; BEAT=60/DRUM_BPM; BARL=BEAT*4
# musical EQ + glue, leave a pocket for vocals, warm not harsh
chop=fx(Pedalboard([
    HighpassFilter(150), LowShelfFilter(220,2.0),
    PeakFilter(2200,-2.5,1.2),           # carve where a rap voice sits
    HighShelfFilter(9000,1.5,0.7),       # gentle air
    Compressor(threshold_db=-18,ratio=2.0,attack_ms=15,release_ms=180),
]),chop)
chop=saturate(chop,6.0,0.18)             # tasteful warmth/grit
chop=fx(Pedalboard([Reverb(room_size=0.18,wet_level=0.10,dry_level=0.95,width=0.9)]),chop)
n=int(0.05*SR); fi=np.linspace(0,1,n)
chop[:, :n]=chop[:, -n:]*fi[::-1]+chop[:, :n]*fi
chop=chop/np.max(np.abs(chop))*0.9
LOOPN=chop.shape[1]; BARS=int(round(LOOPN/(BARL*SR)))

# ================= homage brass stab (tamed) =================
oth=load_stem("other")
ostab=speedup(oth[:, int(CHOP_START*SR):int((CHOP_START+0.55*BAR)*SR)].copy())[:, :int(0.34*SR)]
g=np.ones(ostab.shape[1]); a=int(0.006*SR); d=int(0.18*SR)
g[:a]=np.linspace(0,1,a); g[-d:]*=np.linspace(1,0,d)
ostab=fx(Pedalboard([HighpassFilter(500),LowpassFilter(4500),
                     PeakFilter(1500,2,1.0)]),ostab*g)
ostab=ostab/(np.max(np.abs(ostab))+1e-9)*0.5

# ================= DRUMS from real one-shots =================
K=load_oneshot(find("kicks","kick-02","kick-01"))
S=load_oneshot(find("snares","snare-01"))
CL=load_oneshot(find("claps","vintage-clap","clap"))
HC=load_oneshot(find("hi-hats","closed","ch"))
HO=load_oneshot(find("open-hats","open-hat","oh"))
SHK=load_oneshot(find("percs","maraca"))
N=LOOPN
def newtr(): return np.zeros((2,N),np.float32)
def place(tr,snd,t,g=1.0,pan=0.0):
    i=int(t*SR)
    if i>=N: return
    m=min(snd.shape[1],N-i)
    l=g*(1-max(0,pan)); r=g*(1+min(0,pan))
    tr[0,i:i+m]+=snd[0,:m]*l; tr[1,i:i+m]+=snd[1,:m]*r

kick=newtr(); snr=newtr(); hats=newtr(); kenv=np.zeros(N)
for b in range(BARS):
    b0=b*BARL
    for kt,kg in [(0,1.0),(0.75*BEAT,0.45),(2.5*BEAT,0.8)]:
        place(kick,K,b0+kt,kg); 
        ii=int((b0+kt)*SR)
        if ii<N: kenv[ii]=1
    for st in [1,3]:
        place(snr,S,b0+st*BEAT,0.85); place(snr,CL,b0+st*BEAT,0.9)
    for j in range(8):
        t=b0+j*(BEAT/2)+(0.008 if j%2 else 0)
        place(hats, HO if j==7 else HC, t, 0.5 if j==7 else 0.4*(0.85+0.3*np.random.rand()),
              pan=0.15 if j%2 else -0.1)
        if j%2: place(hats,SHK,t,0.5,pan=-0.2)

# per-bus pedalboard processing
kick=fx(Pedalboard([HighpassFilter(28),PeakFilter(60,3,1.0),
                    Compressor(threshold_db=-12,ratio=3,attack_ms=8,release_ms=120)]),kick)
kick=saturate(kick,5,0.15)
snr=fx(Pedalboard([HighpassFilter(180),PeakFilter(220,2,1.0),HighShelfFilter(8000,3,0.7),
                   Compressor(threshold_db=-16,ratio=3,attack_ms=4,release_ms=120),
                   Reverb(room_size=0.22,wet_level=0.12,dry_level=0.95,width=1.0)]),snr)
snr=saturate(snr,7,0.16)
hats=fx(Pedalboard([HighpassFilter(400),HighShelfFilter(9000,2,0.7)]),hats)
drums=kick+snr+hats
# drum-bus glue + tasteful targeted distortion (dialed back)
drums=fx(Pedalboard([Compressor(threshold_db=-14,ratio=2.5,attack_ms=12,release_ms=160)]),drums)
drums=saturate(drums,8,0.16)
drums=fx(Pedalboard([Limiter(threshold_db=-1.0)]),drums)

# sidechain pump
sc=np.ones(N)
for i in np.where(kenv>0)[0]:
    dur=int(0.16*SR); seg=np.linspace(0.55,1,dur); e=min(dur,N-i)
    sc[i:i+e]=np.minimum(sc[i:i+e],seg[:e])
sc=np.stack([sc,sc])

# ================= 808 from real sample, tuned to key (D) =================
raw808=load_oneshot(glob.glob(f"{KIT}/808s/*808-lofi*")[0] if glob.glob(f"{KIT}/808s/*808-lofi*") else glob.glob(f"{KIT}/808s/*")[0])
mono808=raw808[0]
# detect fundamental
f0=librosa.yin(mono808,fmin=30,fmax=200,sr=SR)
root_hz=float(np.median(f0[np.isfinite(f0)]))
def note808(freq,dur):
    r=root_hz/freq
    s=librosa.resample(mono808,orig_sr=SR,target_sr=int(SR*r))   # lower pitch -> longer
    s=s[:int(dur*SR)] if len(s)>int(dur*SR) else np.pad(s,(0,int(dur*SR)-len(s)))
    env=np.ones(len(s)); rel=int(0.04*SR); env[-rel:]*=np.linspace(1,0,rel)
    return np.stack([s,s])*env
D2=73.42
sub=newtr()
for b in range(BARS):
    b0=b*BARL
    for (tt,nt,dd) in [(0,D2,BEAT*2.3),(2.5*BEAT,D2*2**(-2/12),BEAT*1.4),(3.5*BEAT,D2*2**(3/12),BEAT*0.6)]:
        place(sub,note808(nt,dd),b0+tt,0.8)
sub=fx(Pedalboard([HighpassFilter(30),LowpassFilter(180),
                   Compressor(threshold_db=-18,ratio=3,attack_ms=10,release_ms=140)]),sub)
sub=saturate(sub,4,0.12)

# ================= ARRANGE =================
blocks=[
 dict(s=1.0,dr=0.0,bs=0.0,stab=True, lp=1500),
 dict(s=1.0,dr=1.0,bs=1.0,stab=True, lp=None),
 dict(s=1.0,dr=1.0,bs=1.0,stab=False,lp=None),
 dict(s=1.0,dr=1.0,bs=1.0,stab=True, lp=None),
 dict(s=1.0,dr=1.0,bs=1.0,stab=False,lp=None),
 dict(s=0.9,dr=0.0,bs=0.7,stab=True, lp=1100),
 dict(s=1.0,dr=1.0,bs=1.0,stab=True, lp=None),
 dict(s=1.0,dr=0.5,bs=0.4,stab=False,lp=1600),
]
pieces=[]
for blk in blocks:
    s=chop.copy()
    if blk["lp"]: s=fx(Pedalboard([LowpassFilter(blk["lp"])]),s)*1.12
    d=drums*blk["dr"]; bs=sub*blk["bs"]
    if blk["dr"]>0: s=s*(0.62+0.38*sc); bs=bs*sc
    stabtr=newtr()
    if blk["stab"]:
        for b in range(0,BARS,2):
            place(stabtr,ostab,b*BARL,1.0)
        if blk["dr"]>0: stabtr=stabtr*(0.62+0.38*sc)
    pieces.append(s*0.95+d+bs+stabtr*0.5)
out=np.concatenate(pieces,axis=1)

# ================= MASTER bus =================
out=fx(Pedalboard([
    HighpassFilter(30),
    LowShelfFilter(90,1.5,0.7),
    HighShelfFilter(11000,1.5,0.7),
    Compressor(threshold_db=-12,ratio=2.0,attack_ms=20,release_ms=200),
    Limiter(threshold_db=-0.8,release_ms=120),
]),out)
out=out/np.max(np.abs(out))*0.97
fi=int(0.05*SR); fo=int(1.0*SR)
out[:, :fi]*=np.linspace(0,1,fi); out[:, -fo:]*=np.linspace(1,0,fo)
sf.write(f"{BASE}/renders/flip_v4.wav",out.T,SR)
print(f"v4 OK | stems={VEXT} | {DRUM_BPM:.1f}BPM +{SEMIS}semi | 808 root {root_hz:.1f}Hz "
      f"| loop {LOOPN/SR:.2f}s ({BARS} bars) | total {out.shape[1]/SR:.1f}s")
