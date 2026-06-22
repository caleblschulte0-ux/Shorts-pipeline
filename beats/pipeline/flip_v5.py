#!/usr/bin/env python3
"""After You've Gone -> homage flip v5.
FEATURE THE SONG: long intact phrase, chords preserved (vocals+bass+tamed
instrumental), modest pitch-up so it's still recognizable. Real drums SUPPORT
the sample. Gold Digger philosophy: the sample is the star.
"""
import sys, numpy as np, librosa, soundfile as sf, glob, os
from pedalboard import (Pedalboard, Compressor, Reverb, Distortion, Limiter,
                        HighShelfFilter, LowShelfFilter, PeakFilter,
                        HighpassFilter, LowpassFilter)
np.random.seed(21)
SR=44100
BASE="/home/user/Shorts-pipeline/beats"
KIT=f"{BASE}/kit/soulful-vintage"
STEM=f"{BASE}/stems/htdemucs/After_Youve_Gone"
ORIG=117.454; BAR=60/ORIG*4

START=float(sys.argv[1]) if len(sys.argv)>1 else 48.19
NBARS=8                      # long, intact -> the melody/changes play through
SEMIS=4                      # modest: bright but still recognizably the song
NAME=sys.argv[2] if len(sys.argv)>2 else "A"

def fx(b,x): return b(x.astype(np.float32),SR)
def sat(x,drive,mix):
    w=Pedalboard([Distortion(drive_db=drive)])(x.astype(np.float32),SR)
    m=max(np.max(np.abs(x)),1e-9); wm=max(np.max(np.abs(w)),1e-9); w=w*(m/wm)
    return (x*(1-mix)+w*mix).astype(np.float32)
def st(name):
    y,_=librosa.load(f"{STEM}/{name}.mp3",sr=SR,mono=False)
    return y if y.ndim==2 else np.stack([y,y])
def one(p):
    y,_=librosa.load(p,sr=SR,mono=True); return np.stack([y,y]).astype(np.float32)
def find(sub,*ns):
    for n in ns:
        g=glob.glob(f"{KIT}/{sub}/*{n}*")
        if g: return g[0]
    return glob.glob(f"{KIT}/{sub}/*")[0]
ratio=2**(SEMIS/12)
def speed(seg): return np.stack([librosa.resample(seg[c],orig_sr=SR,target_sr=int(SR/ratio)) for c in range(2)])
def cut(stem): return stem[:, int(START*SR):int((START+NBARS*BAR)*SR)].copy()

# ===== SAMPLE BED = the song (vocals + chords + bass), brass tamed =====
voc=speed(cut(st("vocals")))
bass=speed(cut(st("bass")))
oth=speed(cut(st("other")))     # piano/strings + brass
# tame brass: roll off top, notch the blatty 1.2-3.5k, drop level
oth=fx(Pedalboard([LowpassFilter(3600), PeakFilter(2000,-6,1.1),
                   PeakFilter(1200,-3,1.0), HighShelfFilter(3000,-4,0.7)]),oth)*0.75
# vocal forward, warm, small pocket carve
voc=fx(Pedalboard([HighpassFilter(140), PeakFilter(2400,-2,1.3),
                   HighShelfFilter(9000,1.5,0.7)]),voc)
bass=fx(Pedalboard([HighpassFilter(45), LowpassFilter(3000)]),bass)*0.9
bed = voc*1.0 + oth*0.85 + bass*0.8
# glue + warmth on the bed, gentle vinyl character
bed=fx(Pedalboard([Compressor(threshold_db=-18,ratio=2,attack_ms=20,release_ms=200),
                   LowpassFilter(13000)]),bed)
bed=sat(bed,5,0.14)
# seamless loop
n=int(0.06*SR); fi=np.linspace(0,1,n)
bed[:, :n]=bed[:, -n:]*fi[::-1]+bed[:, :n]*fi
bed=bed/np.max(np.abs(bed))*0.92
LOOPN=bed.shape[1]
DRUM_BPM=ORIG*ratio/2; BEAT=60/DRUM_BPM; BARL=BEAT*4
BARS=int(round(LOOPN/(BARL*SR)))

# ===== DRUMS (real, SUPPORTING - lower in mix) =====
K=one(find("kicks","kick-02","kick-01")); S=one(find("snares","snare-01"))
CL=one(find("claps","vintage-clap")); HC=one(find("hi-hats","closed"))
HO=one(find("open-hats","open")); SHK=one(find("percs","maraca"))
N=LOOPN
def tr(): return np.zeros((2,N),np.float32)
def place(t_,s,tt,g=1.0,pan=0.0):
    i=int(tt*SR)
    if i>=N: return
    m=min(s.shape[1],N-i)
    t_[0,i:i+m]+=s[0,:m]*g*(1-max(0,pan)); t_[1,i:i+m]+=s[1,:m]*g*(1+min(0,pan))
kick=tr(); snr=tr(); hats=tr(); kenv=np.zeros(N)
for b in range(BARS):
    b0=b*BARL
    for kt,kg in [(0,1.0),(1.75*BEAT,0.4),(2.5*BEAT,0.75)]:
        place(kick,K,b0+kt,kg)
        ii=int((b0+kt)*SR); 
        if ii<N: kenv[ii]=1
    for s_ in [1,3]:
        place(snr,S,b0+s_*BEAT,0.8); place(snr,CL,b0+s_*BEAT,0.85)
    for j in range(8):
        t=b0+j*(BEAT/2)+(0.008 if j%2 else 0)
        place(hats,HO if j==7 else HC,t,0.45 if j==7 else 0.34*(0.85+0.3*np.random.rand()),
              pan=0.15 if j%2 else -0.1)
        if j%2: place(hats,SHK,t,0.45,pan=-0.2)
kick=sat(fx(Pedalboard([HighpassFilter(28),Compressor(threshold_db=-12,ratio=3,attack_ms=8,release_ms=120)]),kick),5,0.12)
snr=sat(fx(Pedalboard([HighpassFilter(180),HighShelfFilter(8000,2,0.7),
        Compressor(threshold_db=-16,ratio=3,attack_ms=4,release_ms=120),
        Reverb(room_size=0.2,wet_level=0.1,dry_level=0.95)]),snr),6,0.12)
hats=fx(Pedalboard([HighpassFilter(400),HighShelfFilter(9000,2,0.7)]),hats)
drums=fx(Pedalboard([Compressor(threshold_db=-14,ratio=2.2,attack_ms=12,release_ms=160),
                     Limiter(threshold_db=-1.5)]),kick+snr+hats)
drums=sat(drums,7,0.12)

# light sub reinforcement under original bass (homage keeps the real bass)
sc=np.ones(N)
for i in np.where(kenv>0)[0]:
    dur=int(0.14*SR); seg=np.linspace(0.7,1,dur); e=min(dur,N-i); sc[i:i+e]=np.minimum(sc[i:i+e],seg[:e])
sc=np.stack([sc,sc])

# ===== ARRANGE: sample-forward, room to rap =====
blocks=[
 dict(dr=0.0,lp=1600,sg=1.0),  # intro: just the song (filtered)
 dict(dr=0.0,lp=None,sg=1.0),  # song clear, no drums (homage statement)
 dict(dr=0.85,lp=None,sg=1.0),
 dict(dr=0.85,lp=None,sg=1.0),
 dict(dr=0.0,lp=1200,sg=0.95), # break
 dict(dr=0.85,lp=None,sg=1.0),
 dict(dr=0.85,lp=None,sg=1.0),
 dict(dr=0.45,lp=1700,sg=1.0), # outro
]
pieces=[]
for blk in blocks:
    s=bed.copy()*blk["sg"]
    if blk["lp"]: s=fx(Pedalboard([LowpassFilter(blk["lp"])]),s)*1.1
    d=drums*blk["dr"]
    if blk["dr"]>0: s=s*(0.72+0.28*sc)   # gentle duck, sample stays loud
    pieces.append(s*1.0 + d*0.82)         # drums SUPPORT (lower)
out=np.concatenate(pieces,axis=1)
out=fx(Pedalboard([HighpassFilter(30),LowShelfFilter(90,1.2,0.7),HighShelfFilter(11000,1.2,0.7),
                   Compressor(threshold_db=-12,ratio=2,attack_ms=20,release_ms=200),
                   Limiter(threshold_db=-0.8,release_ms=120)]),out)
out=out/np.max(np.abs(out))*0.97
fi=int(0.05*SR); fo=int(1.0*SR)
out[:, :fi]*=np.linspace(0,1,fi); out[:, -fo:]*=np.linspace(1,0,fo)
sf.write(f"{BASE}/renders/flip_v5{NAME}.wav",out.T,SR)
print(f"v5{NAME} | start {START}s {NBARS}bars +{SEMIS}semi | {DRUM_BPM:.1f}BPM | loop {LOOPN/SR:.2f}s ({BARS}b) | {out.shape[1]/SR:.1f}s")
