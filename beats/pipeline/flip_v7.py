#!/usr/bin/env python3
"""After You've Gone -> v7. Tighter chop, FULL warm record (brass only gently
tamed), pure-resample (no goofy stretch), drums balanced LOUD with the vocal,
and a real payoff drop (build -> crash + impact + full beat). Same words."""
import numpy as np, librosa, soundfile as sf, glob
from pedalboard import (Pedalboard, Compressor, Reverb, Distortion, Limiter,
                        HighShelfFilter, LowShelfFilter, PeakFilter,
                        HighpassFilter, LowpassFilter)
np.random.seed(7); SR=44100
B="/home/user/Shorts-pipeline/beats"; KIT=f"{B}/kit/soulful-vintage"
STEM=f"{B}/stems/htdemucs/After_Youve_Gone"; SRC=f"{B}/source/After_Youve_Gone.mp3"
ORIG=117.454; BAR=60/ORIG*4
START=104.13; NBARS=4; SEMIS=5            # tighter 4-bar chop; +5 pure resample

def fx(b,x): return b(x.astype(np.float32),SR)
def sat(x,drive,mix):
    w=Pedalboard([Distortion(drive_db=drive)])(x.astype(np.float32),SR)
    m=max(np.max(np.abs(x)),1e-9); w=w*(m/max(np.max(np.abs(w)),1e-9))
    return (x*(1-mix)+w*mix).astype(np.float32)
def rms(x): return float(np.sqrt(np.mean(x**2))+1e-12)
def one(p):
    y,_=librosa.load(p,sr=SR,mono=True); return np.stack([y,y]).astype(np.float32)
def find(sub,*ns):
    for n in ns:
        g=glob.glob(f"{KIT}/{sub}/*{n}*")
        if g: return g[0]
    return glob.glob(f"{KIT}/{sub}/*")[0]

# ============ SAMPLE: full warm record, brass only gently tamed ============
mix,_=librosa.load(SRC,sr=SR,mono=False); mix=mix if mix.ndim==2 else np.stack([mix,mix])
oth,_=librosa.load(f"{STEM}/other.mp3",sr=SR,mono=False); oth=oth if oth.ndim==2 else np.stack([oth,oth])
def cut(x): return x[:, int(START*SR):int((START+NBARS*BAR)*SR)].copy()
samp=cut(mix); brass=cut(oth)
brass_band=fx(Pedalboard([HighpassFilter(1100),LowpassFilter(4200)]),brass)
samp=samp-0.25*brass_band                 # GENTLE tame, keep the instruments
ratio=2**(SEMIS/12)
samp=np.stack([librosa.resample(samp[c],orig_sr=SR,target_sr=int(SR/ratio)) for c in range(2)])  # pure resample
samp=fx(Pedalboard([HighpassFilter(110), LowShelfFilter(220,2.0,0.7),
                    PeakFilter(1900,-2.0,1.1), LowpassFilter(13500),
                    Compressor(threshold_db=-20,ratio=2,attack_ms=25,release_ms=220),
                    HighShelfFilter(9000,1.5,0.7)]),samp)
samp=sat(samp,4,0.10)
# tight loop on the bar grid; derive drum tempo from the sample so they lock
Msec=samp.shape[1]/SR; BARS=max(1,round(Msec/(60/78.4*4)))
BARL=Msec/BARS; BEAT=BARL/4; DRUM_BPM=60/BEAT
loop=samp.copy()
xf=int(0.02*SR); fin=np.sqrt(np.linspace(0,1,xf)); fout=np.sqrt(np.linspace(1,0,xf))
loop[:, -xf:]=loop[:, -xf:]*fout+loop[:, :xf]*fin
loop=loop/np.max(np.abs(loop))*0.92
SAMP_RMS=rms(loop)

# ============ bass notes (musical 808) ============
bass,_=librosa.load(f"{STEM}/bass.mp3",sr=SR,mono=True)
bseg=bass[int(START*SR):int((START+NBARS*BAR)*SR)]; half=BAR/2; midis=[]
for i in range(NBARS*2):
    s=bseg[int(i*half*SR):int((i+1)*half*SR)]
    f0=librosa.yin(s,fmin=40,fmax=300,sr=SR); midis.append(int(round(69+12*np.log2(np.median(f0[np.isfinite(f0)])/440)))+SEMIS)
def root_at(i): return midis[i%len(midis)]

# ============ DRUMS (punchy, simple, hard) ============
K=one(find("kicks","kick-02")); S=one(find("snares","snare-01"))
CL=one(find("claps","vintage-clap")); HC=one(find("hi-hats","closed"))
HO=one(find("open-hats","open")); SHK=one(find("percs","maraca")); CY=one(find("fx","cymbal"))
def render_drums(nbars,fill=False):
    N=int(nbars*BARL*SR); k=np.zeros((2,N),np.float32); sn=np.zeros((2,N),np.float32)
    h=np.zeros((2,N),np.float32); kenv=np.zeros(N)
    def put(t_,s,tt,g=1.,pan=0.):
        i=int(tt*SR)
        if i<0 or i>=N: return
        m=min(s.shape[1],N-i); t_[0,i:i+m]+=s[0,:m]*g*(1-max(0,pan)); t_[1,i:i+m]+=s[1,:m]*g*(1+min(0,pan))
    SW=0.016
    for b in range(nbars):
        b0=b*BARL
        for kt,kg in [(0,1.0),(1.5*BEAT,0.6),(2.5*BEAT,0.8)]:
            put(k,K,b0+kt,kg); ii=int((b0+kt)*SR)
            if 0<=ii<N: kenv[ii]=1
        for sb in [1,3]:
            put(sn,S,b0+sb*BEAT,0.95); put(sn,CL,b0+sb*BEAT,0.85)
        put(sn,S,b0+3.5*BEAT,0.16)            # one ghost
        for j in range(8):
            t=b0+j*(BEAT/2)+(SW if j%2 else 0)
            put(h, HO if j==7 else HC, t, 0.5 if j==7 else 0.34*(0.8+0.4*np.random.rand()),
                pan=0.12 if j%2 else -0.08)
        for j in [1,3,5,7]: put(h,SHK,b0+j*(BEAT/2)+SW,0.38,pan=-0.18)
        if fill and b==nbars-1:
            for r in range(4): put(sn,S,b0+3*BEAT+r*(BEAT/4),0.35+0.18*r)
    k=sat(fx(Pedalboard([HighpassFilter(28),PeakFilter(70,3,1),
            Compressor(threshold_db=-11,ratio=4,attack_ms=6,release_ms=110)]),k),6,0.14)
    sn=sat(fx(Pedalboard([HighpassFilter(170),PeakFilter(210,2,1),HighShelfFilter(7500,3,0.7),
            Compressor(threshold_db=-14,ratio=4,attack_ms=3,release_ms=110),
            Reverb(room_size=0.2,wet_level=0.1,dry_level=0.96)]),sn),7,0.14)
    h=fx(Pedalboard([HighpassFilter(380),HighShelfFilter(9500,2,0.7)]),h)
    d=fx(Pedalboard([Compressor(threshold_db=-12,ratio=2.5,attack_ms=10,release_ms=140),
                     Limiter(threshold_db=-1.0)]),k+sn+h)
    return sat(d,8,0.14), kenv

# ============ 808 (clean, follows roots) ============
raw=one(glob.glob(f"{KIT}/808s/*808-lofi*")[0])[0]
f0=librosa.yin(raw,fmin=30,fmax=200,sr=SR); ROOT=float(np.median(f0[np.isfinite(f0)]))
def note808(m,dur):
    fr=440*2**((m-69)/12); r=ROOT/fr
    s=librosa.resample(raw,orig_sr=SR,target_sr=int(SR*r))
    s=s[:int(dur*SR)] if len(s)>int(dur*SR) else np.pad(s,(0,int(dur*SR)-len(s)))
    e=np.ones(len(s)); e[:200]*=np.linspace(0,1,200); e[-int(0.05*SR):]*=np.linspace(1,0,int(0.05*SR))
    return np.stack([s,s])*e
def render_808(nbars):
    N=int(nbars*BARL*SR); t=np.zeros((2,N),np.float32)
    def put(s,tt,g=1.):
        i=int(tt*SR)
        if i>=N: return
        m=min(s.shape[1],N-i); t[:,i:i+m]+=s[:,:m]*g
    for b in range(nbars):
        b0=b*BARL; bi=b*2
        put(note808(root_at(bi),BEAT*1.6),b0+0,1.0)
        put(note808(root_at(bi+1),BEAT*1.3),b0+2.5*BEAT,0.85)
    t=fx(Pedalboard([HighpassFilter(30),LowpassFilter(160),
                     Compressor(threshold_db=-15,ratio=3,attack_ms=10,release_ms=130)]),t)
    return sat(t,4,0.10)

# ============ balance drums ~EQUAL with the sample ============
_d,_=render_drums(BARS); DRUM_RMS=rms(_d)
DG=(SAMP_RMS/DRUM_RMS)*1.05     # drums slightly hotter than sample
print(f"sample_rms {SAMP_RMS:.3f} drum_rms {DRUM_RMS:.3f} -> drum gain {DG:.2f}")

# ============ FX ============
def reverse_cym(dur):
    s=CY[:, ::-1].copy(); need=int(dur*SR)
    s=s[:, :need] if s.shape[1]>=need else np.pad(s,((0,0),(need-s.shape[1],0)))
    return fx(Pedalboard([HighpassFilter(2200)]),s*(np.linspace(0,1,s.shape[1])**1.4))*0.6
def riser(dur):
    n=int(dur*SR); s=np.random.randn(2,n).astype(np.float32)*(np.linspace(0,1,n)**2)*0.3
    return fx(Pedalboard([HighpassFilter(1600),LowpassFilter(9500)]),s)
def crash(): return fx(Pedalboard([HighpassFilter(400)]),CY.copy())*0.7   # forward = crash
def impact():
    n=int(1.6*SR); t=np.arange(n)/SR; f=np.linspace(80,32,n)
    s=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*2.2)+np.random.randn(n)*np.exp(-t*26)*0.3
    return fx(Pedalboard([LowpassFilter(220)]),np.stack([s,s])*1.0)

# ============ ARRANGE: build -> big payoff drop ============
def tile(loop,nbars):
    need=int(nbars*BARL*SR); reps=int(np.ceil(need/loop.shape[1])); return np.tile(loop,(1,reps))[:, :need]
plan=[("intro",4,0.0,650,False,True),
      ("DROP",8,1.0,None,True,False),
      ("break",2,0.0,1000,False,True),
      ("DROP",8,1.0,None,True,False),
      ("outro",2,0.5,1500,False,False)]
total=sum(p[1] for p in plan); TN=int(total*BARL*SR); out=np.zeros((2,TN),np.float32)
sfull=tile(loop,total); bp=0
for (lab,nb,dg,lp,drop,rise) in plan:
    a=int(bp*BARL*SR); b=int((bp+nb)*BARL*SR); seg=sfull[:, a:b].copy()
    if lp: 
        # intro filter rises across its bars for anticipation
        seg=fx(Pedalboard([LowpassFilter(lp)]),seg)*1.1
        if lab=="intro":
            half=seg.shape[1]//2
            seg[:, half:]=fx(Pedalboard([LowpassFilter(1500)]),sfull[:, a+half:b])*1.1
    drums,kenv=render_drums(nb,fill=(lab=="break")); sub=render_808(nb)
    sc=np.ones(drums.shape[1])
    for i in np.where(kenv>0)[0]:
        du=int(0.12*SR); s2=np.linspace(0.72,1,du); e=min(du,len(sc)-i); sc[i:i+e]=np.minimum(sc[i:i+e],s2[:e])
    sc=np.stack([sc,sc]); sl=min(seg.shape[1],drums.shape[1])
    s_=seg[:, :sl]; d_=drums[:, :sl]*(DG*dg); u_=sub[:, :sl]*(1.0 if dg>0.4 else 0.0)
    if dg>0: s_=s_*(0.82+0.18*sc[:, :sl]); u_=u_*sc[:, :sl]
    blk=s_+d_+u_*0.95
    if drop:
        im=impact(); cr=crash()
        for f_,g in [(im,0.95),(cr,0.8)]:
            m=min(f_.shape[1],blk.shape[1]); blk[:, :m]+=f_[:, :m]*g
    out[:, a:a+blk.shape[1]]+=blk
    if rise:
        rl=int(2*BARL*SR); st=b-rl
        for f_ in (reverse_cym(2*BARL),riser(2*BARL)):
            m=min(f_.shape[1],TN-st)
            if st>=0: out[:, st:st+m]+=f_[:, :m]*0.7
    bp+=nb

out=fx(Pedalboard([HighpassFilter(28),LowShelfFilter(95,1.5,0.7),PeakFilter(350,-1,1),
                   HighShelfFilter(11500,2,0.7),
                   Compressor(threshold_db=-10,ratio=2,attack_ms=20,release_ms=200),
                   Limiter(threshold_db=-0.6,release_ms=110)]),out)
out=out/np.max(np.abs(out))*0.97
fi=int(0.04*SR); fo=int(0.7*SR); out[:, :fi]*=np.linspace(0,1,fi); out[:, -fo:]*=np.linspace(1,0,fo)
sf.write(f"{B}/renders/flip_v7.wav",out.T,SR)
print(f"v7 | {DRUM_BPM:.1f}BPM +{SEMIS}semi pure | loop {loop.shape[1]/SR:.2f}s/{BARS}bars | {total} bars | {out.shape[1]/SR:.1f}s")
