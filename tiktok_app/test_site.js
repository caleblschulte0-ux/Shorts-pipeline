// Offline end-to-end check of the Shorts Media site function: a fake
// Netlify Blobs edge + fake TikTok + fake GitHub + a fake video host that
// serves byte ranges + real RS256 GitHub OIDC tokens, the real handler.
// Run: node tiktok_app/test_site.js [path/to/app.js]
// (tests/test_tiktok_site.py runs it). The 2026-09 ChatGPT build failed
// the callback step here exactly as it failed live.

const http = require("http");
const path = require("path");
process.env.TIKTOK_CLIENT_KEY = "ck"; process.env.TIKTOK_CLIENT_SECRET = "cs"; process.env.SM_COOKIE_SECRET = "cookie";
const mem = new Map(); let n = 0;
// Reads come from `seen`, which lags writes until flush(): Netlify Blobs is
// eventually consistent, and the live site broke on exactly that.
let seen = new Map(); const flush = () => { seen = new Map([...mem].map(([k, v]) => [k, { ...v }])); };
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  const parts = u.pathname.split("/").filter(Boolean); // site, store, ...key
  const key = parts.slice(1).join("/"); // store/key: two stores share one map
  let body = []; req.on("data", (c) => body.push(c)); req.on("end", () => {
    if (req.headers.authorization !== "Bearer blobtok") { res.writeHead(401); return res.end(); }
    if (req.method === "GET" && parts.length <= 2) {
      const p = parts[1] + "/" + (u.searchParams.get("prefix") || "");
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ blobs: [...seen].filter(([k]) => k.startsWith(p)).map(([k, v]) => ({ key: k.slice(parts[1].length + 1), etag: v.etag })) }));
    }
    if (req.method === "GET") { const v = seen.get(key); if (!v) { res.writeHead(404); return res.end(); } res.writeHead(200, { etag: v.etag }); return res.end(v.data); }
    if (req.method === "PUT") {
      const im = req.headers["if-match"]; const cur = mem.get(key);
      if (im && (!cur || cur.etag !== im)) { res.writeHead(412); return res.end(); }
      if (req.headers["if-none-match"] === "*" && cur) { res.writeHead(412); return res.end(); }
      const etag = '"' + (++n) + '"'; mem.set(key, { data: Buffer.concat(body), etag }); res.writeHead(200, { etag }); return res.end();
    }
    if (req.method === "DELETE") { mem.delete(key); res.writeHead(204); return res.end(); }
    res.writeHead(405); res.end();
  });
});
const accountsIn = () => [...mem].filter(([k]) => k.startsWith("site:shorts-media-tiktok-accounts/"));
const realFetch = global.fetch;
let tokenCalls = 0, expiresIn = 86400;
// The fake video host: 11 MB of bytes served by range, like GitHub's CDN.
const BIG = Buffer.alloc(11 * 1024 * 1024, 7); const SMALL = Buffer.alloc(3 * 1024 * 1024, 9);
const hosted = { "https://video.test/big.mp4": BIG, "https://video.test/small.mp4": SMALL };
const uploads = []; let publishStatus = "PROCESSING_UPLOAD";
global.fetch = async (url, opts = {}) => {
  url = String(url);
  if (url.startsWith("https://open.tiktokapis.com/v2/oauth/token/")) {
    tokenCalls++;
    const b = new URLSearchParams(opts.body);
    if (b.get("client_secret") !== "cs") return new Response(JSON.stringify({ error: "invalid_client" }));
    return new Response(JSON.stringify({ access_token: "at" + tokenCalls, refresh_token: "rt" + tokenCalls, open_id: global.NEXT_OPEN_ID || "oid1", expires_in: expiresIn, refresh_expires_in: 31536000, scope: "user.info.basic,video.upload,video.publish" }));
  }
  if (url.startsWith("https://open.tiktokapis.com/v2/user/info/")) return new Response(JSON.stringify({ data: { user: { display_name: "Caleb" } }, error: { code: "ok" } }));
  if (url.startsWith("https://open.tiktokapis.com/v2/post/publish/creator_info/query/")) return new Response(JSON.stringify({ data: { creator_username: global.NEXT_OPEN_ID ? "second" : "thirdbraindown", creator_nickname: "Third", privacy_level_options: ["SELF_ONLY", "PUBLIC_TO_EVERYONE"] }, error: { code: "ok" } }));
  if (url.startsWith("https://open.tiktokapis.com/v2/post/publish/video/init/") || url.startsWith("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/")) {
    const body = JSON.parse(opts.body); uploads.push({ init: body, chunks: [] });
    return new Response(JSON.stringify({ data: { publish_id: "pub" + uploads.length, upload_url: "https://upload.test/" + uploads.length }, error: { code: "ok" } }));
  }
  if (url.startsWith("https://upload.test/")) {
    const up = uploads[Number(url.split("/").pop()) - 1];
    up.chunks.push({ range: opts.headers["Content-Range"], length: opts.body.length });
    const total = up.init.source_info.total_chunk_count;
    return new Response("", { status: up.chunks.length === total ? 201 : 206 });
  }
  if (url.startsWith("https://open.tiktokapis.com/v2/post/publish/status/fetch/")) return new Response(JSON.stringify({ data: { status: publishStatus }, error: { code: "ok" } }));
  if (url.startsWith("https://api.github.com/repos/")) {
    const repo = url.split("/repos/")[1].split("/releases")[0];
    if (repo === "nobody/nothing") return new Response("{}", { status: 404 });
    return new Response(JSON.stringify([
      { tag_name: "v2", name: "Cargo Ships Quietly Got Six Times Bigger", body: "Six times. #ships", published_at: "2026-09-28T00:00:00Z", assets: [{ name: "cargo-ships.mp4", size: BIG.length, browser_download_url: "https://video.test/big.mp4", updated_at: "2026-09-28T00:00:00Z" }, { name: "notes.txt", size: 12, browser_download_url: "https://video.test/notes.txt" }] },
      { tag_name: "v1", name: "first", published_at: "2026-09-20T00:00:00Z", assets: [{ name: "small.mp4", size: SMALL.length, browser_download_url: "https://video.test/small.mp4", updated_at: "2026-09-20T00:00:00Z" }] },
      { tag_name: "d", draft: true, assets: [{ name: "draft.mp4", size: 5, browser_download_url: "https://video.test/draft.mp4" }] }
    ]));
  }
  if (hosted[url]) {
    const buf = hosted[url];
    if ((opts.method || "GET") === "HEAD") return new Response(null, { status: 200, headers: { "content-type": "video/mp4", "content-length": String(buf.length) } });
    const m = /bytes=(\d+)-(\d+)/.exec(opts.headers && opts.headers.Range || "");
    if (!m) return new Response(buf, { status: 200 });
    return new Response(buf.subarray(Number(m[1]), Number(m[2]) + 1), { status: 206 });
  }
  if (url.startsWith("https://token.actions.githubusercontent.com")) return new Response(JSON.stringify({ keys: [Object.assign(global.PUB, { kid: "k1", use: "sig" })] }));
  return realFetch(url, opts);
};
srv.listen(0, async () => {
  const port = srv.address().port;
  const { handler } = require(path.resolve(process.argv[2] || path.join(__dirname, "netlify/functions/app.js")));
  const blobs = Buffer.from(JSON.stringify({ url: `http://127.0.0.1:${port}`, token: "blobtok" })).toString("base64");
  const ev = (p, extra = {}) => Object.assign({ path: p, httpMethod: "GET", headers: { "x-nf-site-id": "site", "x-nf-deploy-id": "d", cookie: extra.cookie || "" }, queryStringParameters: extra.q || {}, blobs }, extra.over || {});
  const post = (p, cookie, fields) => ev(p, { cookie, over: { httpMethod: "POST", body: new URLSearchParams(fields).toString() } });
  const ok = (c, m) => { if (!c) { console.log("FAIL", m); process.exitCode = 1; } else console.log("ok  ", m); };
  const setCookies = (r) => (r.multiValueHeaders && r.multiValueHeaders["Set-Cookie"] || (r.headers["Set-Cookie"] ? [r.headers["Set-Cookie"]] : [])).map((c) => c.split(";")[0]);
  const merge = (cookie, r) => { const jar = Object.fromEntries(cookie.split("; ").filter(Boolean).map((c) => c.split(/=(.*)/s))); for (const c of setCookies(r)) { const [k, v] = c.split(/=(.*)/s); if (v === "") delete jar[k]; else jar[k] = v; } return Object.entries(jar).map(([k, v]) => k + "=" + v).join("; "); };
  let r = await handler(ev("/app"));
  ok(r.statusCode === 200 && /Connect TikTok/.test(r.body) && !/name="repo"/.test(r.body), "library renders for a visitor: connect first, no source forms");
  r = await handler(ev("/app/connect"));
  const loc = new URL(r.headers.Location); const state = loc.searchParams.get("state");
  ok(loc.host === "www.tiktok.com" && loc.searchParams.get("client_key") === "ck" && loc.searchParams.get("scope") === "user.info.basic,video.upload,video.publish", "connect redirects to TikTok with key and the three scopes");
  r = await handler(ev("/auth/tiktok/callback", { q: { code: "c", state }, cookie: "sm_state=" + state }));
  ok(r.statusCode === 200 && /Connected/.test(r.body), "callback stores the account" + (/Connected/.test(r.body) ? "" : " — " + (r.body.match(/status-title">([^<]*)/) || [])[1]));
  ok(accountsIn().length === 1, "one account in Blobs");
  ok(seen.size === 0, "(Blobs has not caught up yet)");
  let cookie = setCookies(r).join("; ");
  r = await handler(ev("/app", { cookie }));
  ok(/TikTok connected/.test(r.body) && /thirdbraindown/.test(r.body) && /No sources yet/.test(r.body), "library shows the connected account before Blobs catches up, empty");
  flush();
  // ---- sources ----
  r = await handler(post("/app/sources", cookie, { action: "add-github", repo: "https://github.com/nobody/nothing" }));
  ok(/no public repository called nobody\/nothing/.test(r.body), "a repository GitHub does not know is reported");
  r = await handler(post("/app/sources", cookie, { action: "add-github", repo: "caleb/videos" }));
  ok(/Added 2 videos from caleb\/videos/.test(r.body) && /Cargo Ships Quietly Got Six Times Bigger/.test(r.body) && /class="vtitle">first</.test(r.body) && !/draft\.mp4|notes\.txt/.test(r.body), "a GitHub repository adds its release videos (not drafts, not text files)");
  cookie = merge(cookie, r);
  r = await handler(ev("/app", { cookie }));
  ok(/still being saved/.test(r.body) && /http-equiv="refresh" content="2"/.test(r.body), "before Blobs catches up the page says the change is saving and refreshes");
  flush();
  r = await handler(ev("/app", { cookie }));
  ok(!/still being saved/.test(r.body) && (r.body.match(/Post to TikTok/g) || []).length === 2 && /GitHub · caleb\/videos/.test(r.body), "after Blobs catches up both videos show with Post buttons");
  const big = (r.body.match(/\/app\/post\/(v[0-9a-f]{16})/g) || []);
  ok(big.length === 2, "each video has its own post link");
  r = await handler(post("/app/sources", cookie, { action: "add-link", url: "https://video.test/small.mp4" }));
  ok(/Added Small/.test(r.body), "a direct link adds one video after a HEAD check");
  cookie = merge(cookie, r); flush();
  r = await handler(post("/app/sources", cookie, { action: "add-link", url: "http://video.test/small.mp4" }));
  ok(/must start with https/.test(r.body), "plain http links are refused");
  r = await handler(post("/app/sources", cookie, { action: "add-sample" }));
  ok(/Added the sample video/.test(r.body) && /Urban Growth/.test(r.body), "the sample video can be added in one click");
  cookie = merge(cookie, r); flush();
  r = await handler(ev("/app", { cookie }));
  ok((r.body.match(/class="source-row"/g) || []).length === 3 && (r.body.match(/Post to TikTok/g) || []).length === 4, "three sources, four videos");
  // ---- composer + chunked posting ----
  const bigId = big.find((l) => l.includes(require("crypto").createHash("sha256").update("https://video.test/big.mp4").digest("hex").slice(0, 16))).split("/").pop();
  r = await handler(ev("/app/post/" + bigId, { cookie }));
  ok(r.statusCode === 200 && /Who can view this video/.test(r.body) && /src="https:\/\/video.test\/big.mp4"/.test(r.body) && /Six times\. #ships/.test(r.body) && /11 MB/.test(r.body), "the composer previews the video from its source with the release notes as caption");
  ok(/media-src 'self' https:/.test(r.headers["Content-Security-Policy"]), "CSP lets the preview play from the video host");
  r = await handler(post("/app/posting", cookie, { video: bigId, caption: "hi", privacy_level: "" }));
  ok(/Pick who can view it/.test(r.body), "posting without a privacy choice is refused");
  r = await handler(post("/app/posting", cookie, { video: bigId, caption: "hi", privacy_level: "SELF_ONLY", allow_comment: "1" }));
  ok(r.statusCode === 302 && /\/app\/status\?id=pub1&v=/.test(r.headers.Location), "posting starts the upload and goes to the status page");
  ok(uploads[0].init.source_info.total_chunk_count === 2 && uploads[0].init.source_info.chunk_size === 5 * 1024 * 1024 && uploads[0].init.post_info.privacy_level === "SELF_ONLY" && uploads[0].init.post_info.disable_comment === false && uploads[0].init.post_info.disable_duet === true, "init declares two chunks (5 MB + the 6 MB rest) with the chosen settings");
  ok(uploads[0].chunks.length === 1 && uploads[0].chunks[0].range === `bytes 0-${5 * 1024 * 1024 - 1}/${BIG.length}`, "the first chunk is sent with the post itself");
  cookie = merge(cookie, r);
  const statusQ = Object.fromEntries(new URL(r.headers.Location).searchParams);
  r = await handler(ev("/app/status", { cookie, q: statusQ }));
  ok(/TikTok is processing your video/.test(r.body) && uploads[0].chunks.length === 2 && uploads[0].chunks[1].range === `bytes ${5 * 1024 * 1024}-${BIG.length - 1}/${BIG.length}` && uploads[0].chunks[1].length === BIG.length - 5 * 1024 * 1024, "the status page sends the last chunk, then waits for TikTok");
  cookie = merge(cookie, r);
  ok(!/sm_upload=[^;]/.test(cookie), "the upload cookie is cleared once every chunk is sent");
  r = await handler(ev("/app/status", { cookie, q: statusQ }));
  ok(/TikTok is processing your video/.test(r.body) && uploads[0].chunks.length === 2, "later refreshes only poll");
  publishStatus = "PUBLISH_COMPLETE";
  r = await handler(ev("/app/status", { cookie, q: statusQ }));
  ok(/Posted to TikTok/.test(r.body) && /visible only to you/.test(r.body) && /Cargo Ships/.test(r.body), "PUBLISH_COMPLETE shows Posted with the audience and the title");
  // a small video: one chunk, sent as a draft
  const smallId = "v" + require("crypto").createHash("sha256").update("https://video.test/small.mp4").digest("hex").slice(0, 16);
  r = await handler(post("/app/drafting", cookie, { video: smallId }));
  ok(r.statusCode === 302 && uploads[1].init.source_info.total_chunk_count === 1 && uploads[1].init.source_info.chunk_size === SMALL.length && uploads[1].chunks.length === 1 && !uploads[1].init.post_info, "a video under 5 MB goes as one chunk; the inbox draft carries no post settings");
  r = await handler(ev("/app/post/vdeadbeefdeadbeef", { cookie }));
  ok(/not in your library/.test(r.body), "an unknown video id is refused");
  // remove a source: its videos go too
  r = await handler(post("/app/sources", cookie, { action: "remove", source: r.body.match(/name="source" value="(github:[^"]+)"/)?.[1] || (await handler(ev("/app", { cookie }))).body.match(/name="source" value="(github:[^"]+)"/)[1] }));
  ok(/Removed\./.test(r.body) && (r.body.match(/Post to TikTok/g) || []).length === 2, "removing the repository removes its two videos");
  flush();
  // ---- accounts (unchanged behaviour) ----
  const [k, v] = [...mem].find(([, x]) => { try { return JSON.parse(x.data).open_id === "oid1"; } catch { return false; } }); const rec = JSON.parse(v.data); rec.access_expires_at = Date.now(); mem.set(k, { data: Buffer.from(JSON.stringify(rec)), etag: v.etag });
  const ownedOnly = cookie.split("; ").filter((c) => c.startsWith("sm_accounts=")).join("");
  r = await handler(ev("/app/connect", { cookie })); const st3 = new URL(r.headers.Location).searchParams.get("state");
  global.NEXT_OPEN_ID = "oid2";
  r = await handler(ev("/auth/tiktok/callback", { q: { code: "c", state: st3 }, cookie: ownedOnly + "; sm_state=" + st3 }));
  global.NEXT_OPEN_ID = undefined;
  const cookie2 = setCookies(r).filter((c) => !c.startsWith("sm_state")).join("; ");
  r = await handler(ev("/app", { cookie: cookie2 }));
  ok(accountsIn().length === 2 && /select\?open_id=oid1/.test(r.body) && /No sources yet/.test(r.body), "a second account links, stays switchable, and has its own empty library");
  r = await handler(ev("/app/connect", { cookie: cookie2 })); const st4 = new URL(r.headers.Location).searchParams.get("state");
  global.NEXT_OPEN_ID = "oid2";
  r = await handler(ev("/auth/tiktok/callback", { q: { code: "c", state: st4 }, cookie: cookie2 + "; sm_state=" + st4 }));
  global.NEXT_OPEN_ID = undefined;
  ok(/\/app\/\?again=1/.test(r.body), "re-linking the same account is called out");
  r = await handler(ev("/app", { cookie: cookie2, q: { again: "1" } }));
  ok(/already connected/.test(r.body), "the page tells you to sign out of tiktok.com first");
  flush();
  await handler(ev("/app/disconnect", { cookie: cookie2 }));
  flush();
  const stale = cookie.replace(/sm_session=[^;]*/, () => { const c = require("crypto"); const body = Buffer.from(JSON.stringify({ open_id: "oid1", tok: "old", exp: 0 })).toString("base64url"); return "sm_session=" + body + "." + c.createHmac("sha256", "cookie").update(body).digest("base64url"); });
  r = await handler(ev("/app", { cookie: stale }));
  const oid1 = accountsIn().map(([, v]) => JSON.parse(v.data)).find((x) => x.open_id === "oid1");
  ok(oid1 && oid1.access_token === "at" + tokenCalls && /TikTok connected/.test(r.body), "expired access token refreshed and saved");
  flush();
  r = await handler(ev("/api/tiktok/token", { over: { httpMethod: "POST", body: "{}" } }));
  ok(r.statusCode === 401, "broker refuses a request without GitHub OIDC");
  r = await handler(Object.assign(ev("/app"), { blobs: undefined }));
  ok(/event.blobs missing/.test(r.body), "missing Blobs says so plainly");
  r = await handler(ev("/app/disconnect", { cookie }));
  ok(r.statusCode === 302 && accountsIn().length === 0, "disconnect removes the account");
  flush();
  // positive broker path: a real RS256 OIDC token for main
  r = await handler(ev("/app/connect")); const st2 = new URL(r.headers.Location).searchParams.get("state");
  await handler(ev("/auth/tiktok/callback", { q: { code: "c", state: st2 }, cookie: "sm_state=" + st2 }));
  flush();
  const crypto = require("crypto");
  const { privateKey, publicKey } = crypto.generateKeyPairSync("rsa", { modulusLength: 2048 });
  global.PUB = publicKey.export({ format: "jwk" });
  const now = Math.floor(Date.now() / 1000);
  const mk = (claims) => { const h = Buffer.from(JSON.stringify({ alg: "RS256", kid: "k1" })).toString("base64url"); const b = Buffer.from(JSON.stringify(claims)).toString("base64url"); return h + "." + b + "." + crypto.sign("RSA-SHA256", Buffer.from(h + "." + b), privateKey).toString("base64url"); };
  const good = { iss: "https://token.actions.githubusercontent.com", aud: "https://shorts-media.netlify.app/api/tiktok/token", repository_id: "1251576094", repository: "caleblschulte0-ux/Shorts-pipeline", ref: "refs/heads/main", event_name: "workflow_run", iat: now, exp: now + 300 };
  const call = (p, jwt, m, body) => handler(Object.assign(ev(p), { httpMethod: m, body, headers: { "x-nf-site-id": "site", "x-nf-deploy-id": "d", authorization: "Bearer " + jwt } }));
  r = await call("/api/tiktok/accounts", mk(good), "GET");
  ok(r.statusCode === 200 && JSON.parse(r.body).accounts[0].handle === "thirdbraindown", "broker lists linked accounts for main");
  r = await call("/api/tiktok/token", mk(good), "POST", JSON.stringify({ handle: "@ThirdBrainDown" }));
  ok(r.statusCode === 200 && JSON.parse(r.body).access_token, "broker hands main a fresh access token");
  r = await call("/api/tiktok/token", mk(Object.assign({}, good, { ref: "refs/heads/claude/x" })), "POST", JSON.stringify({ handle: "thirdbraindown" }));
  ok(r.statusCode === 401, "broker refuses a non-main branch");
  srv.close();
});
