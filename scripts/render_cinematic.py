#!/usr/bin/env python3
"""Cinematic renderer for the explainer channel — the operator-approved v3 look:
big subject PHOTOS + a curiosity hook, an animated photo-card bar race (bars grow,
counters count), a Blender 3D hero that RISES from the floor, a payoff card, the
mascot hosting throughout, edge-tts narration + optional music.

Drives from data_learning/cinematic_stories.json. Renders locally (Blender+Manim
not required — this path uses PIL + Blender only); uploads via uploaders in CI.

  python scripts/render_cinematic.py --story strongest-bite-forces-cine --out out.mp4
  python scripts/render_cinematic.py --story <slug> --upload --publish-at 2026-07-10T21:00:00Z
"""
from __future__ import annotations
import argparse, json, math, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont, ImageFilter

STORIES = ROOT / "data_learning" / "cinematic_stories.json"
BLENDER_PY = ROOT / "data_learning" / "blender_hero.py"
W, H, FPS = 1080, 1920, 30
ACCENT=(79,209,197); GOLD=(245,197,66); BAR=(96,143,217); WHITE=(255,255,255); GRAY=(160,170,190)
FB="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FR="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def _F(sz,bold=True): return ImageFont.truetype(FB if bold else FR, sz)
def _ease(t): return 0 if t<0 else (1 if t>1 else 1-(1-t)**3)


def _story(slug):
    data = json.loads(STORIES.read_text())
    for s in data["stories"]:
        if s["slug"] == slug:
            return s
    raise SystemExit(f"story not found: {slug}")


def _bg():
    top=(9,12,28); bot=(18,24,48); g=Image.new("RGB",(1,H))
    for y in range(H):
        f=y/H; g.putpixel((0,y),tuple(int(top[i]+(bot[i]-top[i])*f) for i in range(3)))
    return g.resize((W,H)).convert("RGBA")


def _glow(img,cx,cy,r,col,a=70):
    o=Image.new("RGBA",(W,H),(0,0,0,0)); ImageDraw.Draw(o).ellipse([cx-r,cy-r,cx+r,cy+r],fill=col+(a,))
    img.alpha_composite(o.filter(ImageFilter.GaussianBlur(120)))


def _fit(im,box):
    im=im.copy(); im.thumbnail((box,box),Image.LANCZOS); return im


def _cutouts(story, work):
    from data_learning import scene_media
    out={}
    for s in story["subjects"]:
        try:
            p=scene_media.subject_cutout(s["query"], story["slug"], s["label"].lower().replace(" ","-"))
            if p and Path(p).exists():
                out[s["label"]]=Image.open(p).convert("RGBA")
        except Exception as e:
            print(f"[cine] cutout miss {s['label']}: {e}", file=sys.stderr)
    return out


def _mascot(work):
    from data_learning import mascot
    p=work/"mascot.png"; mascot.save_static(p, size=420, point_angle=70.0)
    return Image.open(p).convert("RGBA")


def _narrate(text, work, voice="en-US-GuyNeural"):
    mp3=work/"narration.mp3"
    try:
        import edge_tts, asyncio
        async def go(): await edge_tts.Communicate(text, voice, rate="+6%").save(str(mp3))
        asyncio.run(go())
    except Exception as e:
        print(f"[cine] edge-tts failed ({e}); silent", file=sys.stderr); return None,0.0
    d=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","csv=p=0",str(mp3)],capture_output=True,text=True).stdout.strip() or 0)
    return mp3,d


# ---------- segment renderers ----------
def _hook_frames(story, cut, masc, n, d):
    hero_label=story["subjects"][0]["label"]
    for f in range(n):
        t=f/FPS; img=d.copy(); dr=ImageDraw.Draw(img); a=_ease(t/0.5); rise=int((1-a)*60)
        _glow(img,W//2,1060,520,ACCENT,70)
        def ct(txt,fnt,y,fill):
            b=dr.textbbox((0,0),txt,font=fnt); dr.text((W//2-(b[2]-b[0])//2,y),txt,font=fnt,fill=fill)
        ct(story["hook_top"],_F(74),250-rise,WHITE)
        ct(story["hook_big"],_F(120),340-rise,ACCENT)
        ct(story["hook_sub"],_F(40,False),500-rise,GRAY)
        if hero_label in cut:
            im=_fit(cut[hero_label],920); im=Image.blend(Image.new("RGBA",im.size,(0,0,0,0)),im,a)
            img.alpha_composite(im,((W-im.width)//2,780+int((1-a)*40)))
        m=_fit(masc,300); bob=int(8*math.sin(t*2.4)); img.alpha_composite(m,(W-m.width-24,H-m.height-120+bob))
        yield img


def _race_frames(story, cut, masc, n, bg):
    subs=story["subjects"]; VMAX=max(s["value"] for s in subs)
    order=sorted(range(len(subs)),key=lambda i:subs[i]["value"])
    ROW_TOP=600; ROW_H=214; AV=176; BAR_X=330; BAR_MAXW=500; BAR_H=92
    dur=n/FPS; GROW=max(0.8,(dur-2.0)/len(subs)); STAG=GROW*0.72
    start={};
    for k,idx in enumerate(order): start[idx]=0.6+k*STAG
    for f in range(n):
        t=f/FPS; img=bg.copy(); dr=ImageDraw.Draw(img)
        dr.rectangle([0,0,W,10],fill=ACCENT)
        dr.text((60,120),story["kicker"],font=_F(34),fill=ACCENT)
        dr.text((60,172),story["chart_title"],font=_F(72),fill=WHITE)
        dr.rounded_rectangle([60,282,210,294],6,fill=GOLD)
        dr.text((60,322),f'measured in {story["unit"]}',font=_F(36,False),fill=GRAY)
        for i,s in enumerate(subs):
            name=s["label"]; val=s["value"]; y=ROW_TOP+i*ROW_H; cy=y+ROW_H//2-16
            gt=(t-start[i])/GROW; growing=0<=gt<=1; frac=_ease(max(0,min(1,gt)))*val/VMAX
            dr.rounded_rectangle([44,y-6,W-44,y+ROW_H-40],22,fill=(20,27,50))
            sc=1.0+(0.16*math.sin(min(1,max(0,gt))*math.pi) if growing else 0); av=int(AV*sc)
            dr.ellipse([60,cy-av//2,60+av,cy+av//2],fill=(30,40,68))
            if name in cut:
                im=_fit(cut[name],av-10); img.alpha_composite(im,(60+av//2-im.width//2,cy-im.height//2))
            dr.text((BAR_X,cy-AV//2-6),name,font=_F(42),fill=WHITE)
            by0=cy+8
            dr.rounded_rectangle([BAR_X,by0,BAR_X+BAR_MAXW,by0+BAR_H],16,fill=(26,34,60))
            w=int(BAR_MAXW*frac); col=ACCENT if val==VMAX else BAR
            if w>4: dr.rounded_rectangle([BAR_X,by0,BAR_X+w,by0+BAR_H],16,fill=col)
            shown=frac*VMAX
            vt=(f"{shown:,.1f}" if VMAX<100 else f"{int(round(shown)):,}")
            dr.text((BAR_X+w+20,by0+18),vt,font=_F(54),fill=GOLD if val==VMAX else WHITE)
        m=_fit(masc,240); bob=int(8*math.sin(t*2.4)); img.alpha_composite(m,(W-m.width-24,H-m.height-70+bob))
        dr.text((60,H-70),story["source"],font=_F(26,False),fill=GRAY)
        yield img


def _payoff_frames(story, cut, masc, n, bg):
    hero_label=story["subjects"][0]["label"]
    for f in range(n):
        t=f/FPS; img=bg.copy(); dr=ImageDraw.Draw(img); a=_ease(t/0.4)
        _glow(img,W//2,820,480,GOLD,60)
        def ct(txt,fnt,y,fill):
            b=dr.textbbox((0,0),txt,font=fnt); dr.text((W//2-(b[2]-b[0])//2,y),txt,font=fnt,fill=fill)
        if hero_label in cut:
            im=_fit(cut[hero_label],880); im=Image.blend(Image.new("RGBA",im.size,(0,0,0,0)),im,a)
            img.alpha_composite(im,((W-im.width)//2,470))
        ct(story["payoff_big"],_F(150),1150,GOLD)
        yy=1330
        for line in story["payoff_lines"]:
            ct(line,_F(56),yy,WHITE); yy+=70
        dr.rounded_rectangle([(W-160)//2,yy+18,(W+160)//2,yy+30],6,fill=ACCENT)
        ct("follow for more",_F(46,False),yy+62,GRAY)
        m=_fit(masc,260); bob=int(8*math.sin(t*2.4)); img.alpha_composite(m,(W-m.width-24,H-m.height-90+bob))
        yield img


def _dump(frames, d):
    d.mkdir(parents=True, exist_ok=True)
    n=0
    for i,im in enumerate(frames):
        im.convert("RGB").save(d/f"f{i:04d}.png"); n=i+1
    return n


def _blender(story, work, secs):
    subs=story["subjects"]
    spec={"points":[{"label":s["label"],"value":float(s["value"]),"display":s["display"]} for s in subs],
          "accent":"#4FD1C5","seconds":secs,"fps":12,"samples":24,"res_x":1280,"res_y":720,"grow":True}
    sp=work/"bspec.json"; sp.write_text(json.dumps(spec))
    fr=work/"hero"; fr.mkdir(exist_ok=True)
    r=subprocess.run(["blender","-b","--factory-startup","--python",str(BLENDER_PY),"--",
                      str(sp),str(fr)],capture_output=True,text=True)
    if not list(fr.glob("hero_*.png")):
        print("[cine] blender failed:",(r.stderr or "")[-400:],file=sys.stderr); return None
    return fr


def _chrome3d(story, work, masc):
    o=Image.new("RGBA",(W,H),(0,0,0,0)); dr=ImageDraw.Draw(o)
    def ct(t,f,y,c):
        b=dr.textbbox((0,0),t,font=f); dr.text((W//2-(b[2]-b[0])//2,y),t,font=f,fill=c)
    ct("Now — to scale",_F(64),210,WHITE); ct("watch them rise",_F(40,False),300,ACCENT)
    champ=story["subjects"][0]; ct(f'{champ["label"]} leads at {champ["display"]} {story["unit"]}',_F(40),1520,GOLD)
    m=_fit(masc,230); o.alpha_composite(m,(W-m.width-24,H-m.height-90))
    p=work/"chrome3d.png"; o.save(p); return p


def render_story(story, out_mp4, work, music=None):
    work.mkdir(parents=True, exist_ok=True)
    bg=_bg(); cut=_cutouts(story,work); masc=_mascot(work)
    narr,D = _narrate(story["narration"], work)
    total = max(14.0, D+0.6) if D else 16.0
    # allocate
    hook_d=max(2.4,0.16*total); payoff_d=max(3.0,0.17*total); hero_d=0.24*total
    race_d=max(5.0,total-hook_d-payoff_d-hero_d)
    pad="scale=1080:-2:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x0a0e20,setsar=1,format=yuv420p"
    # frame dumps
    _dump(_hook_frames(story,cut,masc,int(hook_d*FPS),bg), work/"s_hook")
    _dump(_race_frames(story,cut,masc,int(race_d*FPS),bg), work/"s_race")
    _dump(_payoff_frames(story,cut,masc,int(payoff_d*FPS),bg), work/"s_payoff")
    hero=_blender(story,work,hero_d); chrome=_chrome3d(story,work,masc)
    def enc(dir_,out): subprocess.run(["ffmpeg","-y","-framerate","30","-i",str(dir_/"f%04d.png"),
        "-vf",f"{pad},fps=30","-c:v","libx264","-pix_fmt","yuv420p",str(out),"-loglevel","error"],check=True)
    enc(work/"s_hook",work/"p_hook.mp4"); enc(work/"s_race",work/"p_race.mp4"); enc(work/"s_payoff",work/"p_payoff.mp4")
    parts=[work/"p_hook.mp4"]
    if hero:
        subprocess.run(["ffmpeg","-y","-framerate","12","-i",str(hero/"hero_%04d.png"),"-i",str(chrome),
            "-filter_complex",f"[0:v]{pad}[bg];[bg][1:v]overlay=0:0,fps=30[v]","-map","[v]",
            "-c:v","libx264","-pix_fmt","yuv420p",str(work/"p_hero.mp4"),"-loglevel","error"],check=True)
    parts=[work/"p_hook.mp4",work/"p_race.mp4"]+([work/"p_hero.mp4"] if hero else [])+[work/"p_payoff.mp4"]
    # durations for xfade
    def dur(p): return float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","csv=p=0",str(p)],capture_output=True,text=True).stdout.strip() or 0)
    inp=[]; [inp.extend(["-i",str(p)]) for p in parts]
    fc=[]; off=0.0; prev="0"; XF=0.4
    for i in range(1,len(parts)):
        off=off+dur(parts[i-1])-XF
        lab=f"x{i}"
        tr="fadeblack" if parts[i].name=="p_hero.mp4" else "fade"
        fc.append(f"[{prev}][{i}]xfade=transition={tr}:duration={XF}:offset={off:.3f}[{lab}]")
        prev=lab
    silent=work/"silent.mp4"
    subprocess.run(["ffmpeg","-y",*inp,"-filter_complex",";".join(fc),"-map",f"[{prev}]",
        "-c:v","libx264","-pix_fmt","yuv420p",str(silent),"-loglevel","error"],check=True)
    # audio: narration (+ optional music duck)
    if narr:
        vdur=dur(silent)
        if music and Path(music).exists():
            subprocess.run(["ffmpeg","-y","-i",str(silent),"-i",str(narr),"-stream_loop","-1","-i",str(music),
                "-filter_complex","[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map","0:v","-map","[a]","-t",str(vdur),"-c:v","copy","-c:a","aac","-movflags","+faststart",
                str(out_mp4),"-loglevel","error"],check=True)
        else:
            subprocess.run(["ffmpeg","-y","-i",str(silent),"-i",str(narr),"-map","0:v","-map","1:a",
                "-c:v","copy","-c:a","aac","-shortest","-movflags","+faststart",str(out_mp4),"-loglevel","error"],check=True)
    else:
        subprocess.run(["ffmpeg","-y","-i",str(silent),"-c","copy",str(out_mp4),"-loglevel","error"],check=True)
    return {"title":story["title"],"tags":story.get("tags",[]),
            "description":f'{story["title"]}\n\n{story["source"]}\n\n#shorts',"duration":dur(out_mp4)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--story",required=True); ap.add_argument("--out",default="")
    ap.add_argument("--music",default=""); ap.add_argument("--upload",action="store_true")
    ap.add_argument("--publish-at",default=""); ap.add_argument("--channel",default="explainer")
    a=ap.parse_args()
    # Dedupe against the explainer posted-log BEFORE rendering: a re-dispatch
    # of the workflow must not upload the same story twice.
    from fsutil import atomic_write_json, load_json
    log_path=ROOT/"state"/"explainer_posted_log.json"
    if a.upload:
        log=load_json(log_path, {"posted": {}})
        if a.story in log.get("posted", {}):
            print(f"[cine] {a.story} already in posted log — skipping")
            return 0
    story=_story(a.story)
    work=Path(tempfile.mkdtemp(prefix="cine_"))
    out=Path(a.out) if a.out else ROOT/f"{a.story}.mp4"
    meta=render_story(story,out,work,music=a.music or None)
    print(f"[cine] rendered {out} ({meta['duration']:.1f}s)")
    if a.upload:
        from datetime import datetime, timezone
        from uploaders import YouTubeUploader
        up=YouTubeUploader(channel=a.channel)
        res=up.upload(str(out),title=meta["title"],description=meta["description"],
                      tags=meta["tags"],publish_at=a.publish_at or None,category="27")
        print(f"[cine] uploaded: {res}")
        # Record the upload immediately — an upload that isn't logged is a
        # duplicate waiting to happen. The workflow persists this file.
        log=load_json(log_path, {"posted": {}})
        log.setdefault("posted", {})[a.story]={
            "url": getattr(res, "url", None) or str(res),
            "title": meta["title"],
            "at": datetime.now(timezone.utc).isoformat(),
            "publish_at": a.publish_at or None,
        }
        atomic_write_json(log_path, log)
    print("CINE_DONE", out)


if __name__=="__main__":
    sys.exit(main())
