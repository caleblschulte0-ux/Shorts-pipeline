"""Large review-only expansion for local, data, web, map, motion and media capabilities."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import csv, json, sqlite3
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from review_prototypes.capability_studio.contracts import CommandPlan, RequestPlan

class ResourceClass(str,Enum): LIGHT="light";MEDIUM="medium";HEAVY="heavy";GPU="gpu"
@dataclass(frozen=True)
class Capability:
    id:str; stages:tuple[str,...]; tools:tuple[str,...]; fallbacks:tuple[str,...]=(); resource:ResourceClass=ResourceClass.LIGHT; network:bool=False; enabled:bool=False; warnings:tuple[str,...]=()
    def validate(self):
        return tuple(x for x,ok in (("id_missing",bool(self.id)),("stage_missing",bool(self.stages)),("tool_missing",bool(self.tools))) if not ok)

def C(id,stages,tools,fallbacks=(),resource=ResourceClass.LIGHT,network=False,enabled=False,warnings=()):return Capability(id,stages,tools,fallbacks,resource,network,enabled,warnings)
R=ResourceClass
CAPABILITIES=(
 C("local-llm-ollama",("discover","script","qa"),("ollama",),("deterministic-writer",),R.HEAVY),
 C("local-llm-llamacpp",("discover","script","qa"),("llama-server",),("ollama","deterministic-writer"),R.HEAVY),
 C("local-embeddings",("discover","qa","learning"),("sentence-transformers",),("tfidf-local",),R.HEAVY),
 C("semantic-vector-index",("discover","learning","storage"),("faiss","sqlite-vec"),("sqlite-fts5",),R.MEDIUM),
 C("rss-atom-discovery",("discover",),("feedparser",),("stdlib-xml",),network=True,enabled=True),
 C("sitemap-discovery",("discover","verify"),("python-stdlib",),("playwright",),network=True,enabled=True),
 C("article-extraction",("verify",),("trafilatura","readability-lxml"),("playwright-dom",),network=True),
 C("structured-data-extraction",("verify",),("extruct",),("stdlib-html",),network=True),
 C("warc-evidence-capture",("verify","package"),("warcio",),("playwright-snapshot",),network=True),
 C("responsive-browser-capture",("verify","build_visuals"),("playwright","chromium"),("wkhtmltoimage",),R.MEDIUM,network=True),
 C("paddleocr-document-vision",("verify",),("paddleocr",),("tesseract",),R.HEAVY),
 C("duckdb-analysis",("verify","script","build_visuals"),("duckdb",),("python-sqlite",),R.MEDIUM,enabled=True),
 C("polars-transform",("verify","build_visuals"),("polars",),("python-csv",),R.MEDIUM),
 C("data-contract-validation",("verify","qa"),("pandera",),("stdlib-validator",),enabled=True),
 C("vega-lite-graphics",("build_visuals",),("vega-lite","vl-convert"),("svg-motion",),R.MEDIUM),
 C("plotly-kaleido-graphics",("build_visuals",),("plotly","kaleido"),("vega-lite","svg-motion"),R.MEDIUM),
 C("lottie-motion",("build_visuals",),("lottie-web","rlottie"),("svg-motion",),R.MEDIUM),
 C("remotion-composition",("build_visuals","edit"),("remotion",),("ffmpeg",),R.HEAVY),
 C("map-data-overpass",("verify","build_visuals"),("overpass-api",),("natural-earth",),network=True),
 C("geocoding-nominatim",("verify","build_visuals"),("nominatim",),("wikidata-coordinates",),network=True,warnings=("Respect instance usage policy.",)),
 C("geospatial-rendering",("build_visuals",),("geopandas","maplibre"),("svg-map",),R.HEAVY),
 C("whisperx-alignment",("narrate","edit"),("whisperx",),("faster-whisper",),R.GPU),
 C("stable-ts-alignment",("narrate","edit"),("stable-whisper",),("faster-whisper",),R.HEAVY),
 C("silero-vad",("narrate","edit","qa"),("silero-vad",),("ffmpeg-silencedetect",),R.MEDIUM),
 C("rnnoise-cleanup",("narrate","edit"),("rnnoise",),("ffmpeg-afftdn",),R.MEDIUM),
 C("librosa-rhythm-grid",("edit","qa"),("librosa",),("ffmpeg-astats",),R.MEDIUM),
 C("karaoke-caption-engine",("edit","build_visuals"),("python-stdlib",),("ass-static-captions",),enabled=True),
 C("optical-flow-analysis",("source_media","edit","qa"),("opencv",),("ffmpeg-mestimate",),R.HEAVY),
 C("smart-auto-reframe",("edit",),("opencv","mediapipe"),("center-crop-blur-fill",),R.HEAVY),
 C("freeze-black-frame-detection",("qa",),("ffmpeg","opencv"),("frame-hash-scan",),enabled=True),
 C("siglip-visual-ranking",("qa","learning"),("transformers",),("clip",),R.GPU),
 C("dinov2-visual-memory",("qa","learning"),("transformers","faiss"),("pillow-phash",),R.GPU),
 C("grounding-dino-localization",("build_visuals","qa"),("groundingdino",),("sam2","opencv"),R.GPU),
 C("argos-local-translation",("script","package"),("argostranslate",),("english-only",),R.MEDIUM),
 C("nllb-localization",("script","package"),("transformers",),("argos-local-translation",),R.GPU),
 C("musicgen-bed",("narrate","edit"),("audiocraft",),("procedural-ffmpeg-music",),R.GPU,warnings=("Validate model/output licensing.",)),
 C("audiogen-sfx",("edit",),("audiocraft",),("procedural-ffmpeg-sfx",),R.GPU,warnings=("Validate model/output licensing.",)),
 C("procedural-sfx",("edit",),("ffmpeg",),enabled=True),
)
CAPABILITY_BY_ID={c.id:c for c in CAPABILITIES}
def validate_catalog():
    failures=[];seen=set()
    for c in CAPABILITIES:
        if c.id in seen:failures.append(f"duplicate:{c.id}")
        seen.add(c.id);failures.extend(f"{c.id}:{x}" for x in c.validate())
    return tuple(failures)
def required_secret_names():return ()

class Need(str,Enum):
 LOCAL_SCRIPT="local_script";SEMANTIC_MEMORY="semantic_memory";WEB_EVIDENCE="web_evidence";DOCUMENT_OCR="document_ocr";DATA_STORY="data_story";MAP_EXPLAINER="map_explainer";MOTION_GRAPHIC="motion_graphic";WORD_SYNC_CAPTIONS="word_sync_captions";AUDIO_REPAIR="audio_repair";SMART_REFRAME="smart_reframe";VISUAL_RETRIEVAL="visual_retrieval";LOCALIZATION="localization";MUSIC_AND_SFX="music_and_sfx"
ROUTES={
 Need.LOCAL_SCRIPT:(("local-llm-ollama","local-llm-llamacpp"),("deterministic-writer",)),
 Need.SEMANTIC_MEMORY:(("local-embeddings","semantic-vector-index"),("sqlite-fts5",)),
 Need.WEB_EVIDENCE:(("rss-atom-discovery","sitemap-discovery","article-extraction","structured-data-extraction","responsive-browser-capture","warc-evidence-capture"),("playwright-snapshot",)),
 Need.DOCUMENT_OCR:(("paddleocr-document-vision",),("ocrmypdf","tesseract")),
 Need.DATA_STORY:(("duckdb-analysis","polars-transform","data-contract-validation","vega-lite-graphics"),("svg-motion",)),
 Need.MAP_EXPLAINER:(("geocoding-nominatim","map-data-overpass","geospatial-rendering"),("svg-map",)),
 Need.MOTION_GRAPHIC:(("lottie-motion","remotion-composition","plotly-kaleido-graphics"),("vega-lite-graphics","svg-motion")),
 Need.WORD_SYNC_CAPTIONS:(("whisperx-alignment","silero-vad","karaoke-caption-engine"),("stable-ts-alignment","faster-whisper")),
 Need.AUDIO_REPAIR:(("rnnoise-cleanup","silero-vad","librosa-rhythm-grid"),("ffmpeg-afftdn",)),
 Need.SMART_REFRAME:(("smart-auto-reframe","optical-flow-analysis","freeze-black-frame-detection"),("center-crop-blur-fill",)),
 Need.VISUAL_RETRIEVAL:(("siglip-visual-ranking","dinov2-visual-memory","grounding-dino-localization"),("clip","pillow-phash")),
 Need.LOCALIZATION:(("nllb-localization",),("argos-local-translation","english-only")),
 Need.MUSIC_AND_SFX:(("musicgen-bed","audiogen-sfx"),("procedural-sfx",)),}
@dataclass(frozen=True)
class RouteRequest: id:str;need:Need;allow_network:bool=True;allow_heavy:bool=True;allow_gpu:bool=False
@dataclass(frozen=True)
class Route: capabilities:tuple[str,...];fallbacks:tuple[str,...];blocked:bool=False;reason:str=""
class Router:
 def route(self,r:RouteRequest,available:Mapping[str,bool]|None=None):
    available=available or {x:True for x in CAPABILITY_BY_ID};primary,fallbacks=ROUTES[r.need];chosen=[]
    for x in primary:
      c=CAPABILITY_BY_ID[x]
      if c.network and not r.allow_network:continue
      if c.resource in {R.HEAVY,R.GPU} and not r.allow_heavy:continue
      if c.resource==R.GPU and not r.allow_gpu:continue
      if available.get(x,False):chosen.append(x)
    if chosen:return Route(tuple(chosen),fallbacks)
    usable=tuple(x for x in fallbacks if available.get(x,True))
    return Route(usable,()) if usable else Route((),fallbacks,True,"no_allowed_capability_or_fallback")

@dataclass(frozen=True)
class LocalPrompt:
 prompt:str;schema:str;max_tokens:int=1200;temperature:float=.3
 def __post_init__(self):
  if not self.prompt.strip() or not self.schema.strip():raise ValueError("prompt/schema required")
  if self.max_tokens<64 or not 0<=self.temperature<=2:raise ValueError("invalid generation settings")
class Planner:
 def ollama(self,r:LocalPrompt,model="qwen2.5:7b"):
  return RequestPlan("ollama","POST","http://127.0.0.1:11434/api/generate",json_body={"model":model,"prompt":r.prompt,"stream":False,"format":"json","options":{"temperature":r.temperature,"num_predict":r.max_tokens}},notes=(f"Validate against {r.schema}.",))
 def llama_server(self,model_path,port=8080):return CommandPlan("llama.cpp",("llama-server","-m",model_path,"--port",str(port),"--host","127.0.0.1"),inputs=(model_path,))
 def embeddings(self,source,out):return CommandPlan("sentence-transformers",("python","-m","review_prototypes.advanced_capabilities","embed","--input",source,"--output",out),inputs=(source,),outputs=(out,))
 def rss(self,url,out):return CommandPlan("feedparser",("python","-m","review_prototypes.advanced_capabilities","rss","--url",url,"--output",out),outputs=(out,))
 def article(self,url,out):return CommandPlan("trafilatura",("python","-m","review_prototypes.advanced_capabilities","article","--url",url,"--output",out),outputs=(out,))
 def browser_capture(self,url,out):return CommandPlan("playwright",("python","-m","review_prototypes.advanced_capabilities","capture","--url",url,"--output",out,"--viewports","390x844,1080x1920,1440x1000"),outputs=(out,))
 def duckdb(self,sources,sql,out):
  if not sources:raise ValueError("sources required")
  return CommandPlan("duckdb",("python","-m","review_prototypes.advanced_capabilities","duckdb","--sql",sql,"--output",out,"--sources",*sources),inputs=(*sources,sql),outputs=(out,))
 def geocode(self,q,user_agent):
  if not q.strip() or not user_agent.strip():raise ValueError("query/user_agent required")
  return RequestPlan("nominatim","GET","https://nominatim.openstreetmap.org/search",headers={"User-Agent":user_agent},query={"q":q,"format":"jsonv2","limit":"5"},notes=("Cache and respect usage policy.",))
 def overpass(self,q):return RequestPlan("overpass","POST","https://overpass-api.de/api/interpreter",json_body={"data":q},notes=("Use bounded cached queries.",))
 def lottie(self,animation,out):return CommandPlan("lottie",("node","lottie_render.mjs","--input",animation,"--output-dir",out),inputs=(animation,),outputs=(out,))
 def remotion(self,composition,props,out):return CommandPlan("remotion",("npx","remotion","render",composition,out,"--props",props),inputs=(props,),outputs=(out,))
 def whisperx(self,audio,out):return CommandPlan("whisperx",("whisperx",audio,"--output_dir",out,"--output_format","json"),inputs=(audio,),outputs=(out,))
 def freeze_black(self,video,log):return CommandPlan("ffmpeg",("ffmpeg","-hide_banner","-i",video,"-vf","blackdetect=d=.25:pix_th=.10,freezedetect=n=-50dB:d=.5","-an","-f","null","-"),inputs=(video,),outputs=(log,),notes=("Capture stderr to log.",))
 def reframe(self,video,tracking,out):return CommandPlan("smart-reframe",("python","-m","review_prototypes.advanced_capabilities","reframe","--video",video,"--tracking",tracking,"--output",out),inputs=(video,tracking),outputs=(out,))
 def translate(self,source,source_lang,target_lang,out,engine="argos"):
  if source_lang==target_lang:raise ValueError("languages must differ")
  return CommandPlan("translation",("python","-m","review_prototypes.advanced_capabilities","translate","--engine",engine,"--input",source,"--source",source_lang,"--target",target_lang,"--output",out),inputs=(source,),outputs=(out,))
 def procedural_sfx(self,out,kind="whoosh",duration=.6):
  if kind not in {"whoosh","impact","riser","notification"}:raise ValueError("bad sfx")
  filters={"whoosh":f"anoisesrc=color=white:duration={duration},highpass=f=300,lowpass=f=5000","impact":f"sine=frequency=70:duration={duration}","riser":f"sine=frequency=220:duration={duration},asetrate=67200,aresample=48000","notification":f"sine=frequency=880:duration={duration}"}
  return CommandPlan("ffmpeg",("ffmpeg","-y","-f","lavfi","-i",filters[kind],"-c:a","pcm_s16le",out),outputs=(out,))

@dataclass(frozen=True)
class Series: id:str;unit:str;geography:str;vintage:str;frequency:str
class DataGate:
 def compare(self,items:Iterable[Series]):
  rows=tuple(items)
  if not rows:return ("no_series",)
  failures=[]
  for attr,name in (("unit","unit_mismatch"),("geography","geography_mismatch"),("vintage","vintage_mismatch"),("frequency","frequency_mismatch")):
   if len({getattr(x,attr) for x in rows})>1:failures.append(name)
  return tuple(failures)
@dataclass(frozen=True)
class Word:text:str;start:float;end:float
class Karaoke:
 def build(self,words:Sequence[Word],max_words=5):
  if not words:raise ValueError("words required")
  header="[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Karaoke,Arial,72,&H00FFFFFF,&H0000D7FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,7,0,2,80,80,280,1\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
  lines=[header]
  def t(s):
   cs=round(s*100);h,r=divmod(cs,360000);m,r=divmod(r,6000);sec,c=divmod(r,100);return f"{h}:{m:02d}:{sec:02d}.{c:02d}"
  for i in range(0,len(words),max_words):
   g=words[i:i+max_words];body=" ".join(f"{{\\k{max(1,round((w.end-w.start)*100))}}}{w.text}" for w in g);lines.append(f"Dialogue: 0,{t(g[0].start)},{t(g[-1].end)},Karaoke,,0,0,0,,{body}\n")
  return "".join(lines)
def fts_index(source,out):
 con=sqlite3.connect(out)
 try:
  con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS records USING fts5(id UNINDEXED,title,text)")
  for line in Path(source).read_text().splitlines():
   if line.strip():
    r=json.loads(line);con.execute("INSERT INTO records VALUES(?,?,?)",(r["id"],r.get("title",""),r.get("text","")))
  con.commit()
 finally:con.close()
def validate_csv(dataset,required):
 with open(dataset,newline="",encoding="utf-8") as h:
  reader=csv.DictReader(h);columns=tuple(reader.fieldnames or ());rows=sum(1 for _ in reader)
 failures=tuple(f"missing_column:{x}" for x in required if x not in columns)
 return {"ok":not failures,"failures":failures,"columns":columns,"rows":rows}
