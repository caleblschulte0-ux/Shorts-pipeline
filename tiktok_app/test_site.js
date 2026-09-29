// Offline end-to-end check of the Shorts Media site function: a fake
// Netlify Blobs edge + fake TikTok + real RS256 GitHub OIDC tokens, the
// real handler. Run: node tiktok_app/test_site.js [path/to/app.js]
// (tests/test_tiktok_site.py runs it). The 2026-09 ChatGPT build failed
// the callback step here exactly as it failed live.

const http = require("http");
const path = require("path");
process.env.TIKTOK_CLIENT_KEY = "ck"; process.env.TIKTOK_CLIENT_SECRET = "cs"; process.env.SM_COOKIE_SECRET = "cookie";
const mem = new Map(); let n = 0;
const srv = http.createServer((req, res) => {
  const u = new URL(req.url, "http://x");
  const parts = u.pathname.split("/").filter(Boolean); // site, store, ...key
  const key = parts.slice(2).join("/");
  let body = []; req.on("data", (c) => body.push(c)); req.on("end", () => {
    if (req.headers.authorization !== "Bearer blobtok") { res.writeHead(401); return res.end(); }
    if (req.method === "GET" && !key) {
      const p = u.searchParams.get("prefix") || "";
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify({ blobs: [...mem].filter(([k]) => k.startsWith(p)).map(([k, v]) => ({ key: k, etag: v.etag })) }));
    }
    if (req.method === "GET") { const v = mem.get(key); if (!v) { res.writeHead(404); return res.end(); } res.writeHead(200, { etag: v.etag }); return res.end(v.data); }
    if (req.method === "PUT") {
      const im = req.headers["if-match"]; const cur = mem.get(key);
      if (im && (!cur || cur.etag !== im)) { res.writeHead(412); return res.end(); }
      const etag = '"' + (++n) + '"'; mem.set(key, { data: Buffer.concat(body), etag }); res.writeHead(200, { etag }); return res.end();
    }
    if (req.method === "DELETE") { mem.delete(key); res.writeHead(204); return res.end(); }
    res.writeHead(405); res.end();
  });
});
const realFetch = global.fetch;
let tokenCalls = 0, expiresIn = 86400;
global.fetch = async (url, opts = {}) => {
  url = String(url);
  if (url.startsWith("https://open.tiktokapis.com/v2/oauth/token/")) {
    tokenCalls++;
    const b = new URLSearchParams(opts.body);
    if (b.get("client_secret") !== "cs") return new Response(JSON.stringify({ error: "invalid_client" }));
    return new Response(JSON.stringify({ access_token: "at" + tokenCalls, refresh_token: "rt" + tokenCalls, open_id: "oid1", expires_in: expiresIn, refresh_expires_in: 31536000, scope: "user.info.basic,video.upload,video.publish" }));
  }
  if (url.startsWith("https://open.tiktokapis.com/v2/user/info/")) return new Response(JSON.stringify({ data: { user: { display_name: "Caleb" } }, error: { code: "ok" } }));
  if (url.startsWith("https://open.tiktokapis.com/v2/post/publish/creator_info/query/")) return new Response(JSON.stringify({ data: { creator_username: "thirdbraindown", creator_nickname: "Third" }, error: { code: "ok" } }));
  if (url.startsWith("https://token.actions.githubusercontent.com")) return new Response(JSON.stringify({ keys: [Object.assign(global.PUB, { kid: "k1", use: "sig" })] }));
  return realFetch(url, opts);
};
srv.listen(0, async () => {
  const port = srv.address().port;
  const { handler } = require(path.resolve(process.argv[2] || path.join(__dirname, "netlify/functions/app.js")));
  const blobs = Buffer.from(JSON.stringify({ url: `http://127.0.0.1:${port}`, token: "blobtok" })).toString("base64");
  const ev = (p, extra = {}) => Object.assign({ path: p, httpMethod: "GET", headers: { "x-nf-site-id": "site", "x-nf-deploy-id": "d", cookie: extra.cookie || "" }, queryStringParameters: extra.q || {}, blobs }, extra.over || {});
  const ok = (c, m) => { if (!c) { console.log("FAIL", m); process.exitCode = 1; } else console.log("ok  ", m); };
  let r = await handler(ev("/app"));
  ok(r.statusCode === 200 && /Connect TikTok/.test(r.body), "library renders, not connected");
  r = await handler(ev("/app/connect"));
  const loc = new URL(r.headers.Location); const state = loc.searchParams.get("state");
  ok(loc.host === "www.tiktok.com" && loc.searchParams.get("client_key") === "ck", "connect redirects to TikTok with key");
  r = await handler(ev("/auth/tiktok/callback", { q: { code: "c", state }, cookie: "sm_state=" + state }));
  ok(r.statusCode === 200 && /Connected/.test(r.body), "callback stores the account" + (/Connected/.test(r.body) ? "" : " — " + (r.body.match(/status-title">([^<]*)/) || [])[1]));
  ok(mem.size === 1, "one account in Blobs");
  const cookie = r.multiValueHeaders["Set-Cookie"].map((c) => c.split(";")[0]).join("; ");
  r = await handler(ev("/app", { cookie }));
  ok(/TikTok connected/.test(r.body) && /thirdbraindown/.test(r.body), "library shows the connected account");
  // expire the access token -> refresh path with etag write
  const [k, v] = [...mem][0]; const rec = JSON.parse(v.data); rec.access_expires_at = Date.now(); mem.set(k, { data: Buffer.from(JSON.stringify(rec)), etag: v.etag });
  r = await handler(ev("/app", { cookie }));
  ok(JSON.parse([...mem][0][1].data).access_token === "at2", "expired access token refreshed and saved");
  r = await handler(ev("/api/tiktok/token", { over: { httpMethod: "POST", body: "{}" } }));
  ok(r.statusCode === 401, "broker refuses a request without GitHub OIDC");
  // no blobs context -> a readable error page, not a crash
  r = await handler(Object.assign(ev("/app"), { blobs: undefined }));
  ok(/event.blobs missing/.test(r.body), "missing Blobs says so plainly");
  r = await handler(ev("/app/disconnect", { cookie }));
  ok(r.statusCode === 302 && mem.size === 0, "disconnect removes the account");
  // positive broker path: a real RS256 OIDC token for main
  r = await handler(ev("/app/connect")); const st2 = new URL(r.headers.Location).searchParams.get("state");
  await handler(ev("/auth/tiktok/callback", { q: { code: "c", state: st2 }, cookie: "sm_state=" + st2 }));
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
