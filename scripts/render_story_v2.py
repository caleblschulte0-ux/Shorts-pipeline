#!/usr/bin/env python3
"""Beats-driven cinematic renderer — the FIX for the repetitive template.

A story is a list of FACTS; each fact names the mechanic that fits it (a size
fact -> scale comparison, a fraction -> a filling meter, a shocking value ->
a counting hero-number). A validator refuses a story that repeats a mechanic,
so no video is bars-bars-bars and no two videos are built the same. Mascot
hosts every beat; real subject photo per noun; everything animates.

  python scripts/render_story_v2.py --story blue-whale-size --out out.mp4
  python scripts/render_story_v2.py --story <slug> --upload --publish-at <iso>
"""
from __future__ import annotations
import argparse, json, math, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont, ImageFilter

STORIES = ROOT / "data_learning" / "cine_stories.json"
BLENDER_PY = ROOT / "data_learning" / "blender_hero.py"
W, H, FPS = 1080, 1920, 30
ACC=(79,209,197); GOLD=(245,197,66); WHITE=(255,255,255); GRAY=(160,170,190)
FB="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def F(s,b=True): return ImageFont.truetype(FB if b else FR,s)
def ease(t): return 0 if t<0 else (1 if t>1 else 1-(1-t)**3)

VALID_MECHANICS = {"scale_compare", "hero_number", "fill_meter"}


def _story(slug):
    for s in json.loads(STORIES.read_text())["stories"]:
        if s.get("slug") == slug:
            return s
    raise SystemExit(f"story not found: {slug}")


def validate(story):
    """No mechanic twice in one video — the anti-repetition rule."""
    mechs = [b["mechanic"] for b in story["beats"]]
    for m in mechs:
        if m not in VALID_MECHANICS:
            raise SystemExit(f"unknown mechanic {m!r}")
    if len(mechs) != len(set(mechs)):
        raise SystemExit(f"variety violation — {story['slug']} repeats a mechanic: {mechs}")


def _bg():
    top=(9,12,28); bot=(18,24,48); g=Image.new("RGB",(1,H))
    for y in range(H): f=y/H; g.putpixel((0,y),tuple(int(top[i]+(bot[i]-top[i])*f) for i in range(3)))
    return g.resize((W,H)).convert("RGBA")


def _glow_layer(cx,cy,r,col,a=70):
    o=Image.new("RGBA",(W,H),(0,0,0,0)); ImageDraw.Draw(o).ellipse([cx-r,cy-r,cx+r,cy+r],fill=col+(a,))
    return o.filter(ImageFilter.GaussianBlur(110))          # computed ONCE per beat


def fit(im,box):
    im=im.copy(); im.thumbnail((box,box),Image.LANCZOS); return im
def fitw(im,wpx):
    r=wpx/im.width; return im.resize((max(1,int(wpx)),max(1,int(im.height*r))),Image.LANCZOS)
def fith(im,hpx):
    r=hpx/im.height; return im.resize((max(1,int(im.width*r)),max(1,int(hpx))),Image.LANCZOS)
def ct(dr,txt,fnt,y,fill,cx=W//2):
    b=dr.textbbox((0,0),txt,font=fnt); dr.text((cx-(b[2]-b[0])//2,y),txt,font=fnt,fill=fill)


class Assets:
    def __init__(self, story, work):
        from data_learning import scene_media, mascot
        self.bg=_bg()
        mascot.save_static(work/"mascot.png", size=420, point_angle=70.0)
        self.masc=Image.open(work/"mascot.png").convert("RGBA")
        self.cut={}
        needed={story["hook"]["subject"], story["payoff"]["subject"]}
        for b in story["beats"]:
            needed.add(b["subject"])
            if b.get("ref"): needed.add(b["ref"])
        for q in needed:
            try:
                p=scene_media.subject_cutout(q, story["slug"], q.replace(" ","-")[:40])
                if p and Path(p).exists(): self.cut[q]=Image.open(p).convert("RGBA")
            except Exception as e:
                print(f"[v2] cutout miss {q}: {e}", file=sys.stderr)
    def img(self,q): return self.cut.get(q)
    def mascot_on(self,img,t,size=240,dy=0):
        m=fit(self.masc,size); bob=int(8*math.sin(t*2.4))
        img.alpha_composite(m,(W-m.width-24,H-m.height-100+dy+bob))


# ---------------- mechanics (each yields frames) ----------------
def m_hook(A, hook, n):
    glow=_glow_layer(W//2,1050,520,ACC,70); sub=A.img(hook["subject"])
    for f in range(n):
        t=f/FPS; img=A.bg.copy(); img.alpha_composite(glow); dr=ImageDraw.Draw(img); a=ease(t/0.5)
        ct(dr,hook["top"],F(70),300-int((1-a)*50),WHITE)
        ct(dr,hook["big"],F(112),392-int((1-a)*50),ACC)
        if sub:
            im=fitw(sub,980); im=Image.blend(Image.new("RGBA",im.size,(0,0,0,0)),im,a)
            img.alpha_composite(im,((W-im.width)//2,900+int((1-a)*40)))
        A.mascot_on(img,t,270); yield img


def m_scale_compare(A, b, n):
    sub=A.img(b["subject"]); ref=A.img(b["ref"]); cnt=int(b.get("ref_count",3)); layout=b.get("layout","row")
    for f in range(n):
        t=f/FPS; img=A.bg.copy(); dr=ImageDraw.Draw(img)
        ct(dr,b["top"],F(56),150,WHITE); ct(dr,b["big"],F(84),225,GOLD)
        if layout=="stack" and sub and ref:
            subimg=fith(sub,1120); img.alpha_composite(subimg,(70,430))
            total=1120; rh=total//cnt-8; r2=fith(ref,rh); x=W-r2.width-120
            for i in range(cnt):
                st=0.25+i*0.12; a=ease((t-st)/0.4)
                if a<=0: continue
                y=430+total-(i+1)*(rh+8)+int((1-a)*40)
                rr=Image.blend(Image.new("RGBA",r2.size,(0,0,0,0)),r2,a)
                img.alpha_composite(rr,(x,y))
        elif sub and ref:
            whale=fitw(sub,1000); img.alpha_composite(whale,((W-whale.width)//2,470))
            total=980; bw=total//cnt-16; r2=fitw(ref,bw); x0=(W-total)//2
            for i in range(cnt):
                st=0.3+i*0.45; a=ease((t-st)/0.45)
                if a<=0: continue
                x=x0+i*(bw+16)-int((1-a)*240)
                rr=Image.blend(Image.new("RGBA",r2.size,(0,0,0,0)),r2,a)
                img.alpha_composite(rr,(x,470-r2.height-30))
        if t>1.8 and b.get("caption"): ct(dr,b["caption"],F(46,False),1560,GRAY)
        A.mascot_on(img,t,220); yield img


def m_hero_number(A, b, n):
    glow=_glow_layer(W//2,780,460,GOLD,55); sub=A.img(b["subject"]); target=float(b["value"]); unit=b.get("unit","")
    for f in range(n):
        t=f/FPS; img=A.bg.copy(); img.alpha_composite(glow); dr=ImageDraw.Draw(img)
        ct(dr,b["top"],F(56),240,WHITE)
        v=ease(min(1,t/1.8))*target
        vt=(f"{v:,.0f}" if target>=100 else f"{v:,.1f}".rstrip("0").rstrip("."))
        if target>=100: vt=f"{round(v,-1):,.0f}"
        ct(dr,f"{vt}{(' '+unit) if unit not in ('%',) else unit}",F(150),380,GOLD)
        if sub:
            im=fitw(sub,540); a=ease((t-0.4)/0.6)
            im=Image.blend(Image.new("RGBA",im.size,(0,0,0,0)),im,max(0,a))
            img.alpha_composite(im,((W-im.width)//2,700))
        if t>1.5 and b.get("compare"): ct(dr,b["compare"],F(48),1280,WHITE)
        A.mascot_on(img,t,220); yield img


def m_fill_meter(A, b, n):
    sub=A.img(b["subject"]); frac=float(b.get("frac",0.7)); col=tuple(b.get("fill_color",[70,140,220]))
    base=fit(sub,820) if sub else None
    for f in range(n):
        t=f/FPS; img=A.bg.copy(); dr=ImageDraw.Draw(img)
        ct(dr,b["top"],F(58),200,WHITE)
        if base:
            bx=(W-base.width)//2; by=430
            dim=Image.new("RGBA",base.size,(0,0,0,0))
            dim.paste(base,(0,0));
            # faint silhouette
            faint=Image.new("RGBA",base.size,(255,255,255,0))
            faint.putalpha(base.split()[-1].point(lambda p:int(p*0.28)))
            img.alpha_composite(Image.composite(Image.new("RGBA",base.size,(60,70,90,255)),
                                                Image.new("RGBA",base.size,(0,0,0,0)),
                                                base.split()[-1]),(bx,by))
            cur=ease(min(1,t/1.6))*frac
            fillh=int(base.height*cur)
            layer=Image.new("RGBA",base.size,(0,0,0,0))
            ld=ImageDraw.Draw(layer); ld.rectangle([0,base.height-fillh,base.width,base.height],fill=col+(255,))
            masked=Image.composite(layer,Image.new("RGBA",base.size,(0,0,0,0)),base.split()[-1])
            img.alpha_composite(masked,(bx,by))
            # outline of full subject on top (light)
            img.alpha_composite(base.point(lambda p:p) if False else base, (bx,by)) if False else None
            pct=int(round(cur*100))
            ct(dr,f"{pct}%",F(150),1300,tuple(col))
        if t>1.6 and b.get("caption"): ct(dr,b["caption"],F(46,False),1490,GRAY)
        A.mascot_on(img,t,220); yield img


def m_payoff(A, p, n):
    glow=_glow_layer(W//2,760,480,ACC,55); sub=A.img(p["subject"])
    for f in range(n):
        t=f/FPS; img=A.bg.copy(); img.alpha_composite(glow); dr=ImageDraw.Draw(img); a=ease(t/0.4)
        if sub:
            im=fitw(sub,900); im=Image.blend(Image.new("RGBA",im.size,(0,0,0,0)),im,a)
            img.alpha_composite(im,((W-im.width)//2,560))
        ct(dr,p["big"],F(150),1120,GOLD)
        yy=1310
        for line in p["lines"]: ct(dr,line,F(56),yy,WHITE); yy+=70
        dr.rounded_rectangle([(W-160)//2,yy+16,(W+160)//2,yy+28],6,fill=ACC)
        ct(dr,"follow for more",F(44,False),yy+58,GRAY)
        A.mascot_on(img,t,240); yield img


MECH = {"scale_compare": m_scale_compare, "hero_number": m_hero_number, "fill_meter": m_fill_meter}


def _narrate(text, work, voice="en-US-GuyNeural"):
    mp3=work/"narration.mp3"
    try:
        import edge_tts, asyncio
        asyncio.run(edge_tts.Communicate(text, voice, rate="+6%").save(str(mp3)))
    except Exception as e:
        print(f"[v2] tts failed ({e}); silent", file=sys.stderr); return None,0.0
    d=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",
        str(mp3)],capture_output=True,text=True).stdout.strip() or 0)
    return mp3,d


def _enc(frames, out, work, idx):
    d=work/f"seg{idx}"; d.mkdir(exist_ok=True)
    for i,im in enumerate(frames): im.convert("RGB").save(d/f"f{i:04d}.png")
    subprocess.run(["ffmpeg","-y","-framerate","30","-i",str(d/"f%04d.png"),
        "-vf","format=yuv420p,fps=30","-c:v","libx264","-pix_fmt","yuv420p",str(out),"-loglevel","error"],check=True)


def render_story(story, out_mp4, work):
    validate(story)
    A=Assets(story, work)
    narr,D=_narrate(story.get("narration",""), work)
    total=max(13.0, D+0.5) if D else 14.5
    nb=len(story["beats"])
    hook_d=max(2.4,0.17*total); payoff_d=max(3.0,0.18*total)
    beat_d=max(3.2,(total-hook_d-payoff_d)/max(1,nb))
    segs=[]; i=0
    def n(sec): return int(sec*FPS)
    _enc(m_hook(A,story["hook"],n(hook_d)), work/f"p{i}.mp4", work, i); segs.append(work/f"p{i}.mp4"); i+=1
    for b in story["beats"]:
        _enc(MECH[b["mechanic"]](A,b,n(beat_d)), work/f"p{i}.mp4", work, i); segs.append(work/f"p{i}.mp4"); i+=1
    _enc(m_payoff(A,story["payoff"],n(payoff_d)), work/f"p{i}.mp4", work, i); segs.append(work/f"p{i}.mp4")
    # crossfade
    def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","csv=p=0",str(p)],capture_output=True,text=True).stdout.strip() or 0)
    inp=[]; [inp.extend(["-i",str(p)]) for p in segs]
    fc=[]; off=0.0; prev="0"; XF=0.4
    for k in range(1,len(segs)):
        off=off+dur(segs[k-1])-XF
        fc.append(f"[{prev}][{k}]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{k}]"); prev=f"x{k}"
    silent=work/"silent.mp4"
    subprocess.run(["ffmpeg","-y",*inp,"-filter_complex",";".join(fc),"-map",f"[{prev}]",
        "-c:v","libx264","-pix_fmt","yuv420p",str(silent),"-loglevel","error"],check=True)
    if narr:
        subprocess.run(["ffmpeg","-y","-i",str(silent),"-i",str(narr),"-map","0:v","-map","1:a",
            "-c:v","copy","-c:a","aac","-shortest","-movflags","+faststart",str(out_mp4),"-loglevel","error"],check=True)
    else:
        subprocess.run(["ffmpeg","-y","-i",str(silent),"-c","copy",str(out_mp4),"-loglevel","error"],check=True)
    return {"title":story["title"],"tags":story.get("tags",[]),
            "description":f'{story["title"]}\n\nIllustrative figures.\n\n#shorts',"duration":dur(out_mp4)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--story",required=True); ap.add_argument("--out",default="")
    ap.add_argument("--upload",action="store_true"); ap.add_argument("--publish-at",default="")
    ap.add_argument("--channel",default="explainer")
    a=ap.parse_args()
    st=_story(a.story); work=Path(tempfile.mkdtemp(prefix="v2_"))
    out=Path(a.out) if a.out else ROOT/f"{a.story}.mp4"
    meta=render_story(st,out,work)
    print(f"[v2] rendered {out} ({meta['duration']:.1f}s), beats={[b['mechanic'] for b in st['beats']]}")
    if a.upload:
        from uploaders import YouTubeUploader
        res=YouTubeUploader(channel=a.channel).upload(str(out),title=meta["title"],
            description=meta["description"],tags=meta["tags"],publish_at=a.publish_at or None,category="27")
        print(f"[v2] uploaded {res}")
    print("V2_DONE", out)


if __name__=="__main__":
    sys.exit(main())
