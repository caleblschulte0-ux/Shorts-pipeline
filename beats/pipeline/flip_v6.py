#!/usr/bin/env python3
"""After You've Gone -> v6 'windows down' flip.
SAMPLE-FIRST (sample the real record, tame brass), seamless musical loop,
soulful bouncy groove with swing, MUSICAL 808 following the song's bassline,
and a real DROP (riser + impact). Built to ride to and rap over.
"""
import numpy as np, librosa, soundfile as sf, glob
from pedalboard import (Pedalboard, Compressor, Reverb, Distortion, Limiter,
                        HighShelfFilter, LowShelfFilter, PeakFilter,
                        HighpassFilter, LowpassFilter, Gain)
np.random.seed(7)
SR=44100
B="/home/user/Shorts-pipeline/beats"
KIT=f"{B}/kit/soulful-vintage"; STEM=f"{B}/stems/htdemucs/After_Youve_Gone"
SRC=f"{B}/source/After_Youve_Gone.mp3"
ORIG=117.454; BAR=60/ORIG*4
START=104.13; NBARS=8; SEMIS=4           # keep v5B words; recognizable pitch

def fx(b,x): return b(x.astype(np.float32),SR)
def sat(x,drive,mix):
    w=Pedalboard([Distortion(drive_db=drive)])(x.astype(np.float32),SR)
    m=max(np.max(np.abs(x)),1e-9); w=w*(m/max(np.max(np.abs(w)),1e-9))
    return (x*(1-mix)+w*mix).astype(np.float32)
def one(p):
    y,_=librosa.load(p,sr=SR,mono=True); return np.stack([y,y]).astype(np.float32)
def find(sub,*ns):
    for n in ns:
        g=glob.glob(f"{KIT}/{sub}/*{n}*")
        if g: return g[0]
    return glob.glob(f"{KIT}/{sub}/*")[0]

# ===================== THE SAMPLE (real record, de-brassed) =====================
mix,_=librosa.load(SRC,sr=SR,mono=False); mix=mix if mix.ndim==2 else np.stack([mix,mix])
oth,_=librosa.load(f"{STEM}/other.mp3",sr=SR,mono=False); oth=oth if oth.ndim==2 else np.stack([oth,oth])
def cut(x): return x[:, int(START*SR):int((START+NBARS*BAR)*SR)].copy()
samp=cut(mix); brass=cut(oth)
# subtract the harsh brass band from the real record (keep warmth + cohesion)
brass_band=fx(Pedalboard([HighpassFilter(900),LowpassFilter(4500)]),brass)
samp=samp-0.55*brass_band
# pitch up (resample) then time-stretch to a rideable tempo (pitch stays +4)
ratio=2**(SEMIS/12)
samp=np.stack([librosa.resample(samp[c],orig_sr=SR,target_sr=int(SR/ratio)) for c in range(2)])
TARGET=172.0                                  # sample tempo -> 86 BPM half-time
cur=ORIG*ratio; rate=TARGET/cur
samp=np.stack([librosa.effects.time_stretch(samp[c],rate=rate) for c in range(2)])
# warm, soulful tone: clear mud, smooth the top (vinyl), small pocket for a voice
samp=fx(Pedalboard([HighpassFilter(120), LowShelfFilter(250,1.5,0.7),
                    PeakFilter(2300,-2,1.2), LowpassFilter(12500),
                    Compressor(threshold_db=-20,ratio=2,attack_ms=25,release_ms=220)]),samp)
samp=sat(samp,4,0.12)

# lock loop to a 4-bar grid; derive drum tempo FROM the sample so they align
Msec=samp.shape[1]/SR
BARS=max(1,round(Msec/(60/86*4))); 
L=int(round((Msec*SR)))                      # use full processed length
BARL=Msec/BARS; BEAT=BARL/4; DRUM_BPM=60/BEAT
loop=samp[:, :L].copy()
# seamless loop: morph the TAIL toward the head (keeps downbeat punchy/clean)
xf=int(0.022*SR); fin=np.sqrt(np.linspace(0,1,xf)); fout=np.sqrt(np.linspace(1,0,xf))
loop[:, -xf:]=loop[:, -xf:]*fout+loop[:, :xf]*fin
loop=loop/np.max(np.abs(loop))*0.92
LSAMP=loop.shape[1]

# ===================== BASS NOTES (musical 808 follows the record) ==============
bass,_=librosa.load(f"{STEM}/bass.mp3",sr=SR,mono=True)
bseg=bass[int(START*SR):int((START+NBARS*BAR)*SR)]
half=BAR/2; midis=[]
for i in range(NBARS*2):
    s=bseg[int(i*half*SR):int((i+1)*half*SR)]
    f0=librosa.yin(s,fmin=40,fmax=300,sr=SR); f=np.median(f0[np.isfinite(f0)])
    midis.append(int(round(69+12*np.log2(f/440)))+SEMIS)   # shift to match sample
# 16 half-bar roots over 8 orig bars == per-beat roots over 4 drum bars
def root_at(beat_idx): return midis[beat_idx % len(midis)]

# ===================== DRUMS (real kit, soulful bounce + swing) =================
K=one(find("kicks","kick-02")); S=one(find("snares","snare-01"))
CL=one(find("claps","vintage-clap")); HC=one(find("hi-hats","closed"))
HO=one(find("open-hats","open")); SHK=one(find("percs","maraca"))
TOTAL_BARS=4
def render_drums(nbars, fill=False):
    N=int(nbars*BARL*SR); k=np.zeros((2,N),np.float32); sn=np.zeros((2,N),np.float32)
    h=np.zeros((2,N),np.float32); kenv=np.zeros(N)
    def put(t_,s,tt,g=1.0,pan=0.0):
        i=int(tt*SR)
        if i>=N or i<0: return
        m=min(s.shape[1],N-i); t_[0,i:i+m]+=s[0,:m]*g*(1-max(0,pan)); t_[1,i:i+m]+=s[1,:m]*g*(1+min(0,pan))
    SW=0.018  # swing delay on offbeats
    for b in range(nbars):
        b0=b*BARL
        # soulful bouncy kick
        for kt,kg in [(0,1.0),(1.5*BEAT,0.55),(2.5*BEAT,0.8),(3.75*BEAT,0.4)]:
            put(k,K,b0+kt,kg); ii=int((b0+kt)*SR)
            if 0<=ii<N: kenv[ii]=1
        # backbeat 2 & 4: snare + clap + a little room
        for sb in [1,3]:
            put(sn,S,b0+sb*BEAT,0.85); put(sn,CL,b0+sb*BEAT,0.8)
        # ghost snares for groove
        put(sn,S,b0+2.75*BEAT,0.18); put(sn,S,b0+3.5*BEAT,0.12)
        # hats: swung 8ths, humanized, open on &-of-4
        for j in range(8):
            t=b0+j*(BEAT/2)+(SW if j%2 else 0)
            put(h, HO if j==7 else HC, t, 0.5 if j==7 else 0.32*(0.8+0.4*np.random.rand()),
                pan=0.12 if j%2 else -0.08)
        # tambourine + shaker drive (summer)
        for j in [1,3,5,7]: put(h,SHK,b0+j*(BEAT/2)+SW,0.4,pan=-0.18)
        # end fill
        if fill and b==nbars-1:
            for r in range(4): put(sn,S,b0+3*BEAT+r*(BEAT/4),0.3+0.15*r)
    # bus processing
    k=sat(fx(Pedalboard([HighpassFilter(28),PeakFilter(70,2,1),
            Compressor(threshold_db=-12,ratio=3,attack_ms=8,release_ms=110)]),k),5,0.12)
    sn=sat(fx(Pedalboard([HighpassFilter(170),HighShelfFilter(8000,2.5,0.7),
            Compressor(threshold_db=-15,ratio=3,attack_ms=4,release_ms=110),
            Reverb(room_size=0.22,wet_level=0.11,dry_level=0.96)]),sn),6,0.12)
    h=fx(Pedalboard([HighpassFilter(380),HighShelfFilter(9500,2,0.7)]),h)
    d=fx(Pedalboard([Compressor(threshold_db=-13,ratio=2.3,attack_ms=12,release_ms=150),
                     Limiter(threshold_db=-1.2)]),k+sn+h)
    return sat(d,7,0.12), kenv

# ===================== 808 (real sample, tuned, musical) =======================
raw=one(glob.glob(f"{KIT}/808s/*808-lofi*")[0])[0]
f0=librosa.yin(raw,fmin=30,fmax=200,sr=SR); ROOT=float(np.median(f0[np.isfinite(f0)]))
def midi_hz(m): return 440*2**((m-69)/12)
def note808(m,dur):
    fr=midi_hz(m); r=ROOT/fr
    s=librosa.resample(raw,orig_sr=SR,target_sr=int(SR*r))
    s=s[:int(dur*SR)] if len(s)>int(dur*SR) else np.pad(s,(0,int(dur*SR)-len(s)))
    e=np.ones(len(s)); rel=int(0.05*SR); e[-rel:]*=np.linspace(1,0,rel); e[:200]*=np.linspace(0,1,200)
    return np.stack([s,s])*e
def render_808(nbars):
    N=int(nbars*BARL*SR); t=np.zeros((2,N),np.float32)
    def put(s,tt,g=0.9):
        i=int(tt*SR)
        if i>=N: return
        m=min(s.shape[1],N-i); t[:,i:i+m]+=s[:,:m]*g
    for b in range(nbars):
        b0=b*BARL; bi=b*4
        # bouncy 808 pattern that follows the roots, leaves pocket
        put(note808(root_at(bi),BEAT*1.4), b0+0)
        put(note808(root_at(bi+1),BEAT*0.6), b0+1.5*BEAT,0.7)
        put(note808(root_at(bi+2),BEAT*1.1), b0+2.5*BEAT,0.85)
        put(note808(root_at(bi+3),BEAT*0.5), b0+3.75*BEAT,0.6)
    t=fx(Pedalboard([HighpassFilter(30),LowpassFilter(170),
                     Compressor(threshold_db=-16,ratio=3,attack_ms=10,release_ms=130)]),t)
    return sat(t,4,0.10)

# ===================== FX: riser + impact =====================================
CY=one(find("fx","cymbal"))
def reverse_cym(dur):
    s=CY[:, ::-1].copy()
    need=int(dur*SR)
    s=s[:, :need] if s.shape[1]>=need else np.pad(s,((0,0),(need-s.shape[1],0)))
    e=np.linspace(0,1,s.shape[1])**1.5
    return fx(Pedalboard([HighpassFilter(2500)]),s*e)*0.5
def riser(dur):
    n=int(dur*SR); s=np.random.randn(2,n).astype(np.float32)
    e=(np.linspace(0,1,n)**2)
    s=s*e*0.25
    return fx(Pedalboard([HighpassFilter(1800),LowpassFilter(9000)]),s)
def impact():
    n=int(1.5*SR); t=np.arange(n)/SR; f=np.linspace(75,32,n)
    s=np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*2.4)
    s+=np.random.randn(n)*np.exp(-t*28)*0.25
    return fx(Pedalboard([LowpassFilter(200)]),np.stack([s,s])*0.9)

# ===================== ARRANGE with a real drop =====================
def tile(loop,nbars):
    need=int(nbars*BARL*SR); reps=int(np.ceil(need/loop.shape[1]))
    return np.tile(loop,(1,reps))[:, :need]
# sections: (label, nbars, drum_gain, sample_lp, drop_impact, riser_into)
plan=[("intro",4,0.0,700,False,True),
      ("drop1",8,1.0,None,True,False),
      ("break",4,0.25,None,False,True),
      ("drop2",8,1.0,None,True,False),
      ("outro",4,0.45,1600,False,False)]
total_bars=sum(p[1] for p in plan)
TN=int(total_bars*BARL*SR)
out=np.zeros((2,TN),np.float32)
sample_full=tile(loop,total_bars)
barpos=0
for (lab,nb,dg,lp,drop,rise) in plan:
    a=int(barpos*BARL*SR); b=int((barpos+nb)*BARL*SR)
    seg=sample_full[:, a:b].copy()
    if lp: seg=fx(Pedalboard([LowpassFilter(lp)]),seg)*1.12
    drums,kenv=render_drums(nb, fill=(lab=="break"))
    sub=render_808(nb)
    # sidechain (sample + sub duck to kick), gentle so sample stays loud
    sc=np.ones(drums.shape[1])
    for i in np.where(kenv>0)[0]:
        du=int(0.13*SR); s2=np.linspace(0.72,1,du); e=min(du,len(sc)-i); sc[i:i+e]=np.minimum(sc[i:i+e],s2[:e])
    sc=np.stack([sc,sc])
    seg_l=min(seg.shape[1],drums.shape[1]); 
    s_=seg[:, :seg_l]; d_=drums[:, :seg_l]*dg; u_=sub[:, :seg_l]*(1.0 if dg>0.4 else 0.0)
    if dg>0: s_=s_*(0.78+0.22*sc[:, :seg_l]); u_=u_*sc[:, :seg_l]
    blk=s_*1.0 + d_*0.8 + u_*0.95
    # drop impact at section start
    if drop:
        im=impact(); m=min(im.shape[1],blk.shape[1]); blk[:, :m]+=im[:, :m]*0.8
    out[:, a:a+blk.shape[1]]+=blk
    # riser INTO the next section (place at end of this section)
    if rise:
        rl=int(2*BARL*SR)
        rc=reverse_cym(2*BARL); rs=riser(2*BARL)
        start=b-rl
        for f_ in (rc,rs):
            m=min(f_.shape[1],TN-start)
            if start>=0: out[:, start:start+m]+=f_[:, :m]*0.6
    barpos+=nb

# ===================== MASTER =====================
out=fx(Pedalboard([HighpassFilter(28),LowShelfFilter(95,1.5,0.7),
                   PeakFilter(350,-1.0,1.0), HighShelfFilter(11000,1.8,0.7),
                   Compressor(threshold_db=-11,ratio=2,attack_ms=20,release_ms=200),
                   Limiter(threshold_db=-0.7,release_ms=110)]),out)
out=out/np.max(np.abs(out))*0.97
fi=int(0.04*SR); fo=int(0.8*SR)
out[:, :fi]*=np.linspace(0,1,fi); out[:, -fo:]*=np.linspace(1,0,fo)
sf.write(f"{B}/renders/flip_v6.wav",out.T,SR)
print(f"v6 | {DRUM_BPM:.1f}BPM (+{SEMIS}semi, stretched) | loop {LSAMP/SR:.2f}s/{BARS}bars "
      f"| {total_bars} bars total | {out.shape[1]/SR:.1f}s | 808 root {ROOT:.0f}Hz")
