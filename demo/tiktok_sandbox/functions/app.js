// Shorts Media — the TikTok Sandbox demo, server-rendered, no page scripts.
//
// One Netlify Function answers every /app/* route and the registered
// callback. The site's CSP is script-src 'none', so every state is a page:
// links, forms and a meta refresh do all the moving. Real TikTok Sandbox:
// real consent screen, real Direct Post (FILE_UPLOAD, one chunk), real
// status polling; posts land on the target user's own account as private.
//
// Secrets live in CONFIG, inlined by build_drop.py from config.json, which
// never leaves the machine that builds the drop.
"use strict";

const crypto = require("crypto");

const CONFIG = __CONFIG__;

const SITE = "https://shorts-media.netlify.app";
const TT = "https://open.tiktokapis.com";
// All three, on the consent screen: who he is, a draft to his inbox
// (video.upload), a post to his profile (video.publish).
const SCOPES = "user.info.basic,video.upload,video.publish";
const VIDEO = {
  id: "urban-growth",
  title: "Urban Growth Just Hit A 50-Year Low Of 1.36%",
  caption: "Everyone assumes cities are exploding faster than ever — but the world's urban growth rate just fell to its slowest pace in over 50 years.\n\n#data #cities #urbanization #explained",
  length: "1:36",
  file: SITE + "/app-assets/media/urban-growth.mp4",
  poster: "/app-assets/media/urban-growth-poster.png",
};
const LIBRARY = [
  { id: "cargo-ships", title: "Cargo Ships Quietly Got Six Times Bigger", length: "0:58", poster: "/app-assets/img/poster-cargo-ships.svg", when: "Yesterday" },
  { id: "ocean-floor", title: "We’ve Mapped More Of Mars Than Our Own Ocean Floor", length: "1:12", poster: "/app-assets/img/poster-ocean-floor.svg", when: "2 days ago" },
  { id: "drinkable-water", title: "How Much Of Earth’s Water You Can Actually Drink", length: "1:04", poster: "/app-assets/img/poster-drinkable-water.svg", when: "3 days ago" },
];

// ---------------------------------------------------------------- helpers

const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" }[c]));

function sign(payload) {
  const body = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const mac = crypto.createHmac("sha256", CONFIG.cookie_secret).update(body).digest("base64url");
  return body + "." + mac;
}

function verify(value) {
  if (!value || value.indexOf(".") < 0) return null;
  const [body, mac] = value.split(".");
  const want = crypto.createHmac("sha256", CONFIG.cookie_secret).update(body).digest("base64url");
  if (mac.length !== want.length || !crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(want))) return null;
  try { return JSON.parse(Buffer.from(body, "base64url").toString("utf8")); } catch { return null; }
}

function cookies(event) {
  const out = {};
  for (const part of String(event.headers.cookie || event.headers.Cookie || "").split(";")) {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

function setCookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}

const BASE_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  "Content-Security-Policy": "default-src 'self'; img-src 'self' data: https:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'none'; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
};

function page(body, extra) {
  return { statusCode: 200, headers: Object.assign({}, BASE_HEADERS, extra || {}), body };
}

function redirect(to, extra) {
  return { statusCode: 302, headers: Object.assign({ Location: to, "Cache-Control": "no-store" }, extra || {}), body: "" };
}

async function tt(path, token, body, method) {
  const res = await fetch(TT + path, {
    method: method || "POST",
    headers: { Authorization: "Bearer " + token, "Content-Type": "application/json; charset=UTF-8" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  const err = json.error || {};
  if (err.code && err.code !== "ok") throw new Error(`${err.code}: ${err.message || ""} (${err.log_id || ""})`);
  return json.data || {};
}

function form(event) {
  const raw = event.isBase64Encoded ? Buffer.from(event.body || "", "base64").toString("utf8") : (event.body || "");
  const out = {};
  for (const [k, v] of new URLSearchParams(raw)) out[k] = v;
  return out;
}

// ---------------------------------------------------------------- markup

const TIKTOK_GLYPH = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M16.6 5.82A4.28 4.28 0 0 1 15.54 3h-3.09v12.4a2.59 2.59 0 0 1-2.59 2.5 2.59 2.59 0 0 1 0-5.18c.27 0 .52.04.76.12v-3.1a5.71 5.71 0 0 0-.76-.05A5.68 5.68 0 1 0 15.54 15.4V9.01a7.35 7.35 0 0 0 4.3 1.38V7.3a4.29 4.29 0 0 1-3.24-1.48z"/></svg>';
const LOCK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>';

function shell(title, main, user) {
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)} | Shorts Media</title>
<meta name="description" content="Shorts Media creator dashboard (TikTok Sandbox).">
<meta name="robots" content="noindex">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" href="/assets/shorts-media-app-icon.png">
<meta name="theme-color" content="#09090c">
<link rel="stylesheet" href="/assets/site.css">
<link rel="stylesheet" href="/app-assets/app.css">
</head>
<body class="app">
<a class="skip" href="#main">Skip to content</a>
<header>
  <div class="shell nav">
    <a class="brand" href="/">
      <img src="/assets/shorts-media-app-icon.png" alt="Shorts Media app icon" width="42" height="42">
      <span>Shorts Media</span>
    </a>
    <nav class="navlinks" aria-label="Support and legal">
      <a href="/support/">Support</a>
      <a href="/privacy-policy/">Privacy Policy</a>
      <a href="/terms-of-service/">Terms of Service</a>
    </nav>
  </div>
  <p class="sandbox-banner">TikTok Sandbox environment — connected to a sandbox app; anything posted goes to your own account as private (Only me).</p>
</header>

<main id="main">
<div class="shell app-shell">
  <div class="appbar">
    <div class="appbar-label">Creator dashboard</div>
    ${acct(user)}
  </div>
${main}
</div>
</main>

<footer>
  <div class="shell app-footer">
    <div>
      <div class="footerbrand">
        <img src="/assets/shorts-media-app-icon.png" alt="" width="40" height="40">
        <span>Shorts Media</span>
      </div>
      <p class="small">TikTok is a third-party service. Shorts Media is not endorsed by, sponsored by, or affiliated with TikTok.</p>
    </div>
    <nav aria-label="More about Shorts Media">
      <a href="/how-it-works/">How it works</a>
      <a href="/data-and-privacy/">Data &amp; privacy controls</a>
    </nav>
  </div>
</footer>
</body>
</html>`;
}

function acct(user) {
  if (!user) {
    return '<div class="acct"><span class="acct-status acct-status-off"><span class="live-dot" aria-hidden="true"></span>TikTok not connected</span></div>';
  }
  return `<div class="acct">
      <div class="acct-pill">
        <img src="${esc(user.avatar)}" alt="TikTok profile photo" width="40" height="40">
        <span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span>
        <span class="acct-status"><span class="live-dot" aria-hidden="true"></span>TikTok connected</span>
      </div>
      <a class="btn btn-quiet" href="/app/disconnect">Disconnect TikTok</a>
    </div>`;
}

function card(v, user, primary) {
  const inner = `<div class="vthumb"><img src="${esc(v.poster)}" alt="" width="1080" height="1920"><span class="dur">${esc(v.length)}</span>${user ? "" : `<span class="lock">${LOCK}Connect TikTok to share</span>`}</div>
<div class="vbody"><div class="vtitle">${esc(v.title)}</div><div class="vsub"><span class="badge ${user ? "badge-ready" : "badge-locked"}">${user ? "Ready" : "Not connected"}</span><span>${esc(v.when || "Today")}</span></div>${user && primary ? `<a class="cta cta-post" href="/app/post/${esc(v.id)}">${TIKTOK_GLYPH}Post to TikTok</a><a class="cta cta-draft" href="/app/draft/${esc(v.id)}">${TIKTOK_GLYPH}Send as a draft</a>` : ""}</div>`;
  return `<div class="vcard">${inner}</div>`;
}

function draftPage(user, video) {
  const main = `
  <div class="page-head">
    <div class="eyebrow">Content Posting API · Upload to inbox</div>
    <h1 class="app-h1">Send to your TikTok inbox as a draft</h1>
    <p class="muted page-lead">The video goes to your TikTok inbox. You finish the caption and settings in the TikTok app; nothing is published by this step.</p>
  </div>
  <form class="composer" action="/app/drafting" method="post">
    <input type="hidden" name="video" value="${esc(video.id)}">
    <div class="composer-cols">
      <div class="composer-preview">
        <div class="flabel" id="preview-label">Preview</div>
        <video class="preview" src="/app-assets/media/${esc(video.id)}.mp4" poster="${esc(video.poster)}" controls preload="metadata" playsinline aria-labelledby="preview-label video-title"></video>
        <p class="video-title" id="video-title">${esc(video.title)}</p>
        <p class="check-line">Video length ${esc(video.length)}</p>
      </div>
      <div class="composer-form">
        <div class="post-account">
          <img src="${esc(user.avatar)}" alt="TikTok profile photo" width="48" height="48">
          <div>
            <div class="post-account-label">Sending to this account's inbox</div>
            <span class="acct-name">${esc(user.name)}</span>
            <span class="acct-handle">@${esc(user.user)}</span>
          </div>
        </div>
        <div class="submit-area">
          <div class="post-wrap"><button type="submit" class="btn-post">${TIKTOK_GLYPH}Send as a draft</button></div>
          <p class="post-note">Nothing is sent to TikTok until you press Send. You will get a notification in the TikTok app to finish the post.</p>
          <div class="cancel-row"><a class="btn btn-quiet" href="/app/">Cancel</a></div>
        </div>
      </div>
    </div>
  </form>`;
  return shell("Send as a draft", main, user);
}

function library(user, notice) {
  const main = `
  <div class="dash-head">
    <div>
      <div class="eyebrow">Library</div>
      <h1 class="app-h1">Your Shorts</h1>
      <p class="muted">${user ? "Post a short straight to your TikTok account. Nothing is sent until you press Post." : "Connect your TikTok account to post these shorts to TikTok."}</p>
    </div>
    ${user ? "" : `<div class="dash-cta">
      <a class="btn btn-tiktok" href="/app/connect">${TIKTOK_GLYPH}Connect TikTok</a>
      <p class="small">You will authorize Shorts Media on TikTok. Shorts Media never asks for your TikTok password.</p>
    </div>`}
  </div>
  ${notice || ""}
  <div class="vgrid">
    ${card(Object.assign({ when: "Today" }, VIDEO), user, true)}${LIBRARY.map((v) => card(v, user, false)).join("")}
  </div>`;
  return shell("Your Shorts", main, user);
}

function composer(user, video, creator) {
  const opts = (creator.privacy_level_options || ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"]);
  const words = { SELF_ONLY: "Only me (private)", MUTUAL_FOLLOW_FRIENDS: "Friends (mutual follows)", FOLLOWER_OF_CREATOR: "Followers", PUBLIC_TO_EVERYONE: "Everyone" };
  const options = opts.map((o) => `<option value="${esc(o)}">${esc(words[o] || o)}</option>`).join("");
  const branded = opts.filter((o) => o !== "SELF_ONLY").map((o) => `<option value="${esc(o)}">${esc(words[o] || o)}</option>`).join("");
  const sw = (id, name, label, disabled, why) => `<div class="switch-row${disabled ? " is-disabled" : ""}">
              <div class="switch-text"><label for="${id}">${label}</label>${disabled ? `<p class="why" id="${id}-why">${esc(why)}</p>` : ""}</div>
              <input class="switch" type="checkbox" id="${id}" name="${name}" value="1"${disabled ? ` disabled aria-describedby="${id}-why"` : ""}>
            </div>`;
  const maxSec = creator.max_video_post_duration_sec ? Math.round(creator.max_video_post_duration_sec / 60) + ":00" : "10:00";
  const main = `
  <div class="page-head">
    <div class="eyebrow">Content Posting API · Direct Post</div>
    <h1 class="app-h1">New TikTok post</h1>
    <p class="muted page-lead">Check the video, edit the caption and choose your settings. Nothing is pre-selected for you.</p>
  </div>
  <form class="composer" action="/app/posting" method="post">
    <input type="hidden" name="video" value="${esc(video.id)}">
    <div class="composer-cols">
      <div class="composer-preview">
        <div class="flabel" id="preview-label">Preview</div>
        <video class="preview" src="/app-assets/media/${esc(video.id)}.mp4" poster="${esc(video.poster)}" controls preload="metadata" playsinline aria-labelledby="preview-label video-title"></video>
        <p class="video-title" id="video-title">${esc(video.title)}</p>
        <p class="check-line">Video length ${esc(video.length)} · within this account's ${esc(maxSec)} maximum</p>
      </div>

      <div class="composer-form">
        <div class="post-account">
          <img src="${esc(user.avatar)}" alt="TikTok profile photo" width="48" height="48">
          <div>
            <div class="post-account-label">Posting to this account</div>
            <span class="acct-name">${esc(user.name)}</span>
            <span class="acct-handle">@${esc(user.user)}</span>
          </div>
        </div>

        <div class="field">
          <label class="flabel" for="caption">Caption</label>
          <textarea id="caption" name="caption" rows="5" maxlength="2200" aria-describedby="caption-hint">${esc(video.caption)}</textarea>
          <p class="hint" id="caption-hint">Edit the caption before posting. Up to 2,200 characters, hashtags included.</p>
        </div>

        <div class="field privacy-standard">
          <label class="flabel" for="privacy">Who can view this video</label>
          <select id="privacy" name="privacy_level" aria-describedby="privacy-hint">
            <option value="" selected>Select who can view this video…</option>
            ${options}
          </select>
          <p class="hint" id="privacy-hint">You must choose. These are the options TikTok allows for this account.</p>
        </div>
        <div class="field privacy-branded">
          <label class="flabel" for="privacy-branded">Who can view this video</label>
          <select id="privacy-branded" name="privacy_level_branded" aria-describedby="privacy-branded-hint">
            <option value="" selected>Select who can view this video…</option>
            <option value="SELF_ONLY" disabled>Only me (not available for branded content)</option>
            ${branded}
          </select>
          <p class="hint" id="privacy-branded-hint">Branded content can't be private, so choose again from the options available.</p>
        </div>

        <fieldset class="field">
          <legend>Allow users to</legend>
          <div class="panel">
            ${sw("allow-comment", "allow_comment", "Comment", !!creator.comment_disabled, "The creator has turned off comments for their account")}
            ${sw("allow-duet", "allow_duet", "Duet", !!creator.duet_disabled, "The creator has turned off Duet for their account")}
            ${sw("allow-stitch", "allow_stitch", "Stitch", !!creator.stitch_disabled, "The creator has turned off Stitch for their account")}
          </div>
        </fieldset>

        <div class="field">
          <div class="panel">
            <div class="switch-row">
              <div class="switch-text">
                <label for="disclose">Disclose video content</label>
                <p class="why" id="disclose-why">Turn on to disclose that this video promotes goods or services in exchange for something of value. Your video could promote yourself, a third party, or both.</p>
              </div>
              <input class="switch" type="checkbox" id="disclose" name="disclose" value="1" aria-describedby="disclose-why">
            </div>
            <div class="disclose-panel">
              <p class="disclose-notice">You need to indicate if your content promotes yourself, a third party, or both.</p>
              <div class="check-row">
                <input class="tick-box" type="checkbox" id="your-brand" name="brand_organic_toggle" value="1" aria-describedby="your-brand-why">
                <div>
                  <label for="your-brand">Your brand</label>
                  <p class="why" id="your-brand-why">You are promoting yourself or your own business. This video will be classified as Brand Organic.</p>
                </div>
              </div>
              <div class="check-row">
                <input class="tick-box" type="checkbox" id="branded-content" name="brand_content_toggle" value="1" aria-describedby="branded-content-why">
                <div>
                  <label for="branded-content">Branded content</label>
                  <p class="why" id="branded-content-why">You are promoting another brand or a third party. This video will be classified as Branded Content.</p>
                </div>
              </div>
              <p class="label-line label-promo">Your photo/video will be labeled as 'Promotional content'</p>
              <p class="label-line label-paid">Your photo/video will be labeled as 'Paid partnership'</p>
            </div>
          </div>
        </div>

        <div class="submit-area">
          <p class="declaration decl-music">By posting, you agree to TikTok's <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener noreferrer">Music Usage Confirmation</a>.</p>
          <p class="declaration decl-branded">By posting, you agree to TikTok's <a href="https://www.tiktok.com/legal/page/global/bc-policy/en" target="_blank" rel="noopener noreferrer">Branded Content Policy</a> and <a href="https://www.tiktok.com/legal/page/global/music-usage-confirmation/en" target="_blank" rel="noopener noreferrer">Music Usage Confirmation</a>.</p>
          <div class="post-wrap">
            <button type="submit" class="btn-post" aria-describedby="post-status post-note">${TIKTOK_GLYPH}Post to TikTok</button>
          </div>
          <div id="post-status">
            <p class="reason reason-privacy">Pick a privacy setting to continue.</p>
            <p class="reason reason-branded-privacy">Branded content can't be private. Pick a privacy setting again to continue.</p>
            <p class="reason reason-disclosure">Choose at least one disclosure option to continue.</p>
            <p class="reason-ready">Ready to post.</p>
          </div>
          <p class="post-note" id="post-note">Nothing is sent to TikTok until you press Post. Your video, caption and settings are only sent after that.</p>
          <div class="cancel-row"><a class="btn btn-quiet" href="/app/">Cancel</a></div>
        </div>
      </div>
    </div>
  </form>`;
  return shell("New TikTok post", main, user);
}

function statusPage(user, video, state, detail, draft) {
  // state: "uploading" | "processing" | "done" | "failed"
  const done = state === "done";
  const failed = state === "failed";
  if (draft) return draftStatus(user, video, state, detail);
  const main = `
  <section class="status-card ${done ? "posted" : "posting"}" aria-labelledby="status-h1">
    <div class="status-top">
      <img class="status-thumb" src="${esc(video.poster)}" alt="Video thumbnail" width="1080" height="1920">
      <div>
        <div class="eyebrow">Content Posting API · Direct Post</div>
        <h1 class="status-h1" id="status-h1">${failed ? "TikTok could not post it" : done ? "Posted to TikTok" : "Posting to TikTok"}</h1>
        <p class="status-title">${esc(video.title)}</p>
        <div class="mini-acct"><img src="${esc(user.avatar)}" alt="" width="36" height="36"><span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span></div>
      </div>
    </div>
    ${failed ? "" : '<div class="progress" aria-hidden="true"><span></span></div>'}
    <ol class="steps">
      <li class="step s1 step-done"><span class="dot" aria-hidden="true"><span class="tick"></span></span>Uploaded to TikTok</li>
      <li class="step s2${state === "uploading" || state === "processing" ? "" : " step-done"}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "TikTok processed your video" : failed ? "TikTok stopped processing" : "TikTok is processing your video…"}</li>
      <li class="step s3${done ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "Posted — visible only to you" : "Waiting for TikTok to confirm"}</li>
    </ol>
    <div class="status-note">
      ${done ? '<p>Your video is on your TikTok profile, visible only to you (Only me). Open your profile to see it.</p>' : failed ? `<p>TikTok answered: ${esc(detail || "no reason given")}.</p>` : "<p>This page checks with TikTok every few seconds. It usually takes under a minute.</p>"}
      <p class="small">TikTok Sandbox — the post is private to your own account.</p>
    </div>
    <div class="status-actions">${done ? `<a class="btn primary btn-wide" href="https://www.tiktok.com/@${esc(user.user)}">Open my TikTok profile</a> <a class="btn btn-quiet" href="/app/">Back to your Shorts</a>` : failed ? '<a class="btn primary btn-wide" href="/app/">Back to your Shorts</a>' : ""}</div>
  </section>`;
  const html = shell(done ? "Posted" : failed ? "Not posted" : "Posting", main, user);
  if (done || failed) return html;
  return html.replace("<title>", '<meta http-equiv="refresh" content="3">\n<title>');
}

function draftStatus(user, video, state, detail) {
  const done = state === "done";
  const failed = state === "failed";
  const main = `
  <section class="status-card ${done ? "posted" : "posting"}" aria-labelledby="status-h1">
    <div class="status-top">
      <img class="status-thumb" src="${esc(video.poster)}" alt="Video thumbnail" width="1080" height="1920">
      <div>
        <div class="eyebrow">Content Posting API · Upload to inbox</div>
        <h1 class="status-h1" id="status-h1">${failed ? "TikTok could not take the draft" : done ? "Draft sent to your TikTok inbox" : "Sending to your TikTok inbox"}</h1>
        <p class="status-title">${esc(video.title)}</p>
        <div class="mini-acct"><img src="${esc(user.avatar)}" alt="" width="36" height="36"><span><span class="acct-name">${esc(user.name)}</span><span class="acct-handle">@${esc(user.user)}</span></span></div>
      </div>
    </div>
    ${failed ? "" : '<div class="progress" aria-hidden="true"><span></span></div>'}
    <ol class="steps">
      <li class="step s1 step-done"><span class="dot" aria-hidden="true"><span class="tick"></span></span>Uploaded to TikTok</li>
      <li class="step s2${done || failed ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "TikTok processed your video" : failed ? "TikTok stopped processing" : "TikTok is processing your video…"}</li>
      <li class="step s3${done ? " step-done" : ""}"><span class="dot" aria-hidden="true"><span class="spin"></span><span class="tick"></span></span>${done ? "In your inbox — finish it in the TikTok app" : "Waiting for TikTok to confirm"}</li>
    </ol>
    <div class="status-note">
      ${done ? "<p>Open the TikTok app: the draft is in your inbox, waiting for your caption and settings. Nothing was published.</p>" : failed ? `<p>TikTok answered: ${esc(detail || "no reason given")}.</p>` : "<p>This page checks with TikTok every few seconds.</p>"}
      <p class="small">TikTok Sandbox — the draft is private to your own account.</p>
    </div>
    <div class="status-actions">${done || failed ? '<a class="btn primary btn-wide" href="/app/">Back to your Shorts</a>' : ""}</div>
  </section>`;
  const html = shell(done ? "Draft sent" : failed ? "Draft not sent" : "Sending", main, user);
  if (done || failed) return html;
  return html.replace("<title>", '<meta http-equiv="refresh" content="3">\n<title>');
}

function problem(user, title, text) {
  const main = `<section class="status-card posting"><div class="status-top"><div><div class="eyebrow">Shorts Media</div><h1 class="status-h1">${esc(title)}</h1><p class="status-title">${esc(text)}</p></div></div><div class="status-actions"><a class="btn primary btn-wide" href="/app/">Back to your Shorts</a></div></section>`;
  return shell(title, main, user);
}

// ---------------------------------------------------------------- routes

exports.handler = async function (event) {
  const path = (event.path || "/").replace(/\/+$/, "") || "/";
  const jar = cookies(event);
  const user = verify(jar.sm_session);
  const q = event.queryStringParameters || {};
  try {
    if (path === "/app") return page(library(user));

    if (path === "/app/connect") {
      const state = crypto.randomBytes(12).toString("base64url");
      const url = "https://www.tiktok.com/v2/auth/authorize/?" + new URLSearchParams({
        client_key: CONFIG.client_key, scope: SCOPES, response_type: "code",
        redirect_uri: CONFIG.redirect_uri, state,
      }).toString();
      return redirect(url, { "Set-Cookie": setCookie("sm_state", state, 600) });
    }

    if (path === "/auth/tiktok/callback") {
      if (q.error) return page(problem(null, "TikTok did not connect", q.error_description || q.error));
      if (!q.code || !q.state || q.state !== jar.sm_state) return page(problem(null, "That link has expired", "Start again from Connect TikTok."));
      const res = await fetch(TT + "/v2/oauth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ client_key: CONFIG.client_key, client_secret: CONFIG.client_secret, code: q.code,
                                    grant_type: "authorization_code", redirect_uri: CONFIG.redirect_uri }).toString(),
      });
      const tok = await res.json().catch(() => ({}));
      if (!tok.access_token) return page(problem(null, "TikTok did not connect", tok.error_description || tok.error || "no token"));
      const info = await tt("/v2/user/info/?fields=open_id,avatar_url,display_name", tok.access_token, undefined, "GET");
      const u = (info.user || {});
      let creator = {};
      try { creator = await tt("/v2/post/publish/creator_info/query/", tok.access_token, {}); } catch (e) { creator = {}; }
      const session = { tok: tok.access_token, open_id: tok.open_id, name: creator.creator_nickname || u.display_name || "TikTok user",
                        user: creator.creator_username || u.display_name || "tiktok", avatar: creator.creator_avatar_url || u.avatar_url || "/app-assets/img/avatar.svg",
                        exp: Date.now() + 1000 * Math.min(Number(tok.expires_in || 3600), 86400) };
      return redirect("/app/", { "Set-Cookie": setCookie("sm_session", sign(session), 86400) });
    }

    if (path === "/app/disconnect") {
      return redirect("/app/", { "Set-Cookie": "sm_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0" });
    }

    if (!user || user.exp < Date.now()) return redirect("/app/");

    if (path === "/app/post/" + VIDEO.id) {
      let creator = {};
      try { creator = await tt("/v2/post/publish/creator_info/query/", user.tok, {}); } catch (e) { creator = {}; }
      return page(composer(user, VIDEO, creator));
    }

    if (path === "/app/posting" && event.httpMethod === "POST") {
      const f = form(event);
      const branded = f.brand_content_toggle === "1";
      const privacy = branded ? f.privacy_level_branded : f.privacy_level;
      if (!privacy) return page(problem(user, "Pick who can view it", "Choose a privacy setting, then post again."));
      if (f.disclose === "1" && !branded && f.brand_organic_toggle !== "1") return page(problem(user, "Say what the video promotes", "Choose at least one disclosure option, then post again."));
      const video = await fetch(VIDEO.file);
      const bytes = Buffer.from(await video.arrayBuffer());
      const init = await tt("/v2/post/publish/video/init/", user.tok, {
        post_info: {
          title: String(f.caption || "").slice(0, 2200),
          privacy_level: privacy,
          disable_comment: f.allow_comment !== "1",
          disable_duet: f.allow_duet !== "1",
          disable_stitch: f.allow_stitch !== "1",
          video_cover_timestamp_ms: 1000,
          brand_content_toggle: branded,
          brand_organic_toggle: f.brand_organic_toggle === "1",
        },
        source_info: { source: "FILE_UPLOAD", video_size: bytes.length, chunk_size: bytes.length, total_chunk_count: 1 },
      });
      const put = await fetch(init.upload_url, {
        method: "PUT",
        headers: { "Content-Type": "video/mp4", "Content-Length": String(bytes.length),
                   "Content-Range": `bytes 0-${bytes.length - 1}/${bytes.length}` },
        body: bytes,
      });
      if (put.status !== 201 && put.status !== 200) return page(problem(user, "The upload did not take", `TikTok answered ${put.status}.`));
      return redirect("/app/status?id=" + encodeURIComponent(init.publish_id));
    }

    if (path === "/app/draft/" + VIDEO.id) return page(draftPage(user, VIDEO));

    if (path === "/app/drafting" && event.httpMethod === "POST") {
      const video = await fetch(VIDEO.file);
      const bytes = Buffer.from(await video.arrayBuffer());
      const init = await tt("/v2/post/publish/inbox/video/init/", user.tok, {
        source_info: { source: "FILE_UPLOAD", video_size: bytes.length, chunk_size: bytes.length, total_chunk_count: 1 },
      });
      const put = await fetch(init.upload_url, {
        method: "PUT",
        headers: { "Content-Type": "video/mp4", "Content-Length": String(bytes.length),
                   "Content-Range": `bytes 0-${bytes.length - 1}/${bytes.length}` },
        body: bytes,
      });
      if (put.status !== 201 && put.status !== 200) return page(problem(user, "The upload did not take", `TikTok answered ${put.status}.`));
      return redirect("/app/status?draft=1&id=" + encodeURIComponent(init.publish_id));
    }

    if (path === "/app/status") {
      const draft = q.draft === "1";
      const st = await tt("/v2/post/publish/status/fetch/", user.tok, { publish_id: String(q.id || "") });
      const s = String(st.status || "");
      if (s === "PUBLISH_COMPLETE" || s === "SEND_TO_USER_INBOX") return page(statusPage(user, VIDEO, "done", "", draft));
      if (s === "FAILED") return page(statusPage(user, VIDEO, "failed", st.fail_reason || "", draft));
      return page(statusPage(user, VIDEO, s === "PROCESSING_UPLOAD" ? "uploading" : "processing", "", draft));
    }

    return redirect("/app/");
  } catch (e) {
    return page(problem(user, "Something went wrong", String(e && e.message || e)));
  }
};
