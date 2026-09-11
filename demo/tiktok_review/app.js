/* Shorts Media — TikTok app-review demo.
 *
 * WHAT THIS IS. A user-facing demonstration of the complete TikTok
 * integration flow, built because TikTok's reviewer asked for one:
 *
 *   "The demo video should show the complete end-to-end flow of the
 *    integrations with TikTok (Please demonstrate with sandbox or provide a
 *    mockup demo). The video should show the user interaction interface,
 *    not the code."
 *
 * WHAT IT IS NOT. It makes no network calls of any kind. `SANDBOX` below is
 * the canned creator_info response a real client would receive from
 * /v2/post/publish/creator_info/query/, and `publish()` simulates the
 * init + upload + processing sequence on a timer. Nothing is posted to any
 * TikTok account, and every screen that could be mistaken for a real result
 * says so. Fabricating a real API call — or implying a live post happened —
 * would be a worse failure than the rejection this exists to fix.
 *
 * THE FORM IS NOT DECORATIVE. Direct Post has UX requirements that a
 * reviewer checks one by one, and each is implemented here as behaviour
 * rather than as a label:
 *
 *   - creator nickname + avatar shown, from creator_info
 *   - privacy MUST be chosen by the user; there is no default, and publish
 *     stays disabled until one is picked
 *   - the privacy options offered are the ones creator_info returns
 *   - Comment / Duet / Stitch all start OFF, and any the creator's own
 *     account disables are locked off with the reason shown
 *   - commercial disclosure defaults OFF; when on, at least one of
 *     "Your brand" / "Branded content" must be chosen
 *   - branded content cannot be posted privately (TikTok forbids it)
 *   - the consent line above the button changes with that choice, and
 *     carries the Music Usage Confirmation / Branded Content Policy links
 *   - nothing uploads until the user presses the button
 */

"use strict";

/* --- The scopes this developer app requests. -----------------------------
 * Every product and scope selected in the TikTok developer application has
 * to be visibly demonstrated in the review video, so they are listed on the
 * consent screen and each one is exercised by the flow below.
 *
 * Confirm this matches your app's Products tab before recording; if you
 * request a scope that never appears in the demo, that alone can fail the
 * review, and a scope you do not actually need is worth removing. */
const SCOPES = [
  { id: "user.info.basic",
    name: "Read your profile info",
    why: "Shows which TikTok account you are posting to (nickname and avatar).",
    product: "Login Kit" },
  { id: "video.publish",
    name: "Post videos to your account",
    why: "Publishes the short you select, with the settings you choose.",
    product: "Content Posting API — Direct Post" },
];

/* --- Canned creator_info response. ---------------------------------------
 * Shape and field names match /v2/post/publish/creator_info/query/ so the
 * demo form is driven by exactly the data the live form would be driven by.
 * `SELF_ONLY` first is deliberate: an unaudited client may only post
 * privately, so this is also what the sandbox really returns. */
const SANDBOX = {
  creator_nickname: "Shorts Media",
  creator_username: "shortsmedia",
  creator_avatar_url: "avatar.svg",
  privacy_level_options: ["SELF_ONLY", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "PUBLIC_TO_EVERYONE"],
  comment_disabled: false,
  duet_disabled: false,
  stitch_disabled: false,
  max_video_post_duration_sec: 600,
};

const PRIVACY_LABELS = {
  PUBLIC_TO_EVERYONE: "Everyone",
  MUTUAL_FOLLOW_FRIENDS: "Friends (mutual follows)",
  FOLLOWER_OF_CREATOR: "Followers",
  SELF_ONLY: "Only me (private)",
};

const MUSIC_URL = "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en";
const BRANDED_URL = "https://www.tiktok.com/legal/page/global/bc-policy/en";

/* The library. One real vertical Short from the channel plus recognisable
 * siblings, so the dashboard reads as a product rather than a test page. */
const LIBRARY = [
  { id: "urban-growth",
    title: "Urban Growth Just Hit A 50-Year Low Of 1.36%",
    caption: "Everyone assumes cities are exploding faster than ever — but the world's urban growth rate just fell to its slowest pace in over 50 years.\n\n#data #cities #urbanization #explained",
    duration: "1:36", created: "Today", src: "media/sample-short.mp4", poster: "media/sample-poster.png" },
  { id: "ocean-floor",
    title: "We've Mapped More Of Mars Than Our Own Ocean Floor",
    caption: "We have better maps of Mars than of the seafloor.\n\n#ocean #space #data",
    duration: "1:12", created: "Yesterday" },
  { id: "cargo-ships",
    title: "Cargo Ships Quietly Got Six Times Bigger",
    caption: "Container ships grew 6x since 1968.\n\n#shipping #data #economy",
    duration: "0:58", created: "2 days ago" },
  { id: "drinkable-water",
    title: "How Much Of Earth's Water You Can Actually Drink",
    caption: "Almost none of it.\n\n#water #earth #data",
    duration: "1:04", created: "3 days ago" },
];

const App = {
  connected: false,
  current: null,
  posted: [],

  /* ---------------- dashboard ---------------- */
  init() {
    this.renderScopes();
    this.renderLibrary();
    document.getElementById("connect-btn")
      .addEventListener("click", () => this.startAuth());
  },

  renderScopes() {
    document.getElementById("scope-list").innerHTML = SCOPES.map(s => `
      <div style="display:flex;gap:11px;align-items:flex-start;margin-bottom:14px">
        <div style="color:var(--gold);font-size:15px;line-height:1.4">●</div>
        <div>
          <div style="font-size:15px;font-weight:600">${s.name}</div>
          <div class="muted" style="margin-top:2px">${s.why}</div>
          <div class="muted" style="margin-top:3px;opacity:.75">${s.product} · <code>${s.id}</code></div>
        </div>
      </div>`).join("");
  },

  card(v, posted) {
    const bg = v.poster ? `background-image:url('${v.poster}')` : "";
    return `
      <div class="card ${!posted && this.current === v.id ? "sel" : ""}"
           ${posted ? "" : `onclick="App.openPost('${v.id}')"`}>
        <div class="thumb" style="${bg}">
          ${v.poster ? "" : `<svg width="42" height="42" viewBox="0 0 24 24" fill="none"
              stroke="#3f4666" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="3"/>
              <path d="M10 9l5 3-5 3z" fill="#3f4666" stroke="none"/></svg>`}
          <span class="dur">${v.duration}</span>
        </div>
        <div class="meta">
          <div class="t">${v.title}</div>
          <div class="d">
            ${posted ? `<span class="badge posted">Posted to TikTok</span>`
                     : `<span class="badge ready">Ready</span>`}
            &nbsp;${posted ? posted : v.created}
          </div>
        </div>
      </div>`;
  },

  renderLibrary() {
    const done = new Set(this.posted.map(p => p.id));
    document.getElementById("library").innerHTML =
      LIBRARY.filter(v => !done.has(v.id)).map(v => this.card(v, null)).join("");

    const wrap = document.getElementById("recent-wrap");
    if (this.posted.length) {
      wrap.classList.remove("hidden");
      document.getElementById("recent").innerHTML = this.posted
        .map(p => this.card(LIBRARY.find(v => v.id === p.id), p.when)).join("");
    } else {
      wrap.classList.add("hidden");
    }
  },

  /* ---------------- auth ---------------- */
  startAuth() { document.getElementById("auth-overlay").classList.remove("hidden"); },
  cancelAuth() { document.getElementById("auth-overlay").classList.add("hidden"); },

  approveAuth() {
    this.connected = true;
    document.getElementById("auth-overlay").classList.add("hidden");
    document.getElementById("connect-btn").classList.add("hidden");

    const pill = document.getElementById("account-pill");
    pill.classList.remove("hidden");
    document.getElementById("acct-nick").textContent = SANDBOX.creator_nickname;
    document.getElementById("acct-avatar").src = SANDBOX.creator_avatar_url;
    document.getElementById("dash-sub").textContent =
      "Select a short to publish to your connected TikTok account.";
  },

  /* ---------------- post sheet ---------------- */
  openPost(id) {
    if (!this.connected) { this.startAuth(); return; }
    const v = LIBRARY.find(x => x.id === id);
    this.current = id;

    document.getElementById("post-nick").textContent = SANDBOX.creator_nickname;
    document.getElementById("post-avatar").src = SANDBOX.creator_avatar_url;

    const vid = document.getElementById("post-video");
    vid.src = v.src || "";
    if (v.poster) vid.poster = v.poster;

    const cap = document.getElementById("caption");
    cap.value = v.caption;
    document.getElementById("cap-count").textContent = cap.value.length;

    // Privacy: rebuilt every time with NO selection, from creator_info.
    const sel = document.getElementById("privacy");
    sel.innerHTML = `<option value="" selected>Select who can view this video…</option>` +
      SANDBOX.privacy_level_options
        .map(p => `<option value="${p}">${PRIVACY_LABELS[p] || p}</option>`).join("");
    sel.classList.add("unset");

    // Interaction toggles: all OFF, and locked off where the creator's own
    // account setting forbids them.
    [["allow-comment", "comment_disabled", "why-comment", "Comments"],
     ["allow-duet", "duet_disabled", "why-duet", "Duet"],
     ["allow-stitch", "stitch_disabled", "why-stitch", "Stitch"]]
      .forEach(([el, flag, whyEl, label]) => {
        const box = document.getElementById(el);
        box.checked = false;
        box.disabled = SANDBOX[flag];
        document.getElementById(whyEl).textContent =
          SANDBOX[flag] ? `${label} is turned off for this account on TikTok.` : "";
      });

    document.getElementById("commercial").checked = false;
    document.getElementById("your-brand").checked = false;
    document.getElementById("branded-content").checked = false;
    document.getElementById("commercial-detail").classList.add("hidden");

    this.refresh();
    document.getElementById("post-overlay").classList.remove("hidden");
  },

  closePost() {
    document.getElementById("post-video").pause();
    document.getElementById("post-overlay").classList.add("hidden");
    this.current = null;
  },

  onCaption() {
    document.getElementById("cap-count").textContent =
      document.getElementById("caption").value.length;
    this.refresh();
  },

  onPrivacy() {
    const sel = document.getElementById("privacy");
    sel.classList.toggle("unset", !sel.value);
    this.refresh();
  },

  onCommercial() {
    const on = document.getElementById("commercial").checked;
    document.getElementById("commercial-detail").classList.toggle("hidden", !on);
    if (!on) {
      document.getElementById("your-brand").checked = false;
      document.getElementById("branded-content").checked = false;
    }
    this.refresh();
  },

  /* The rules that make this a real Direct Post form rather than a mock of
   * one. Recomputed on every interaction so the reviewer can watch the
   * button enable and disable as they go. */
  refresh() {
    const privacy = document.getElementById("privacy").value;
    const commercial = document.getElementById("commercial").checked;
    const brand = document.getElementById("your-brand").checked;
    const branded = document.getElementById("branded-content").checked;

    // Branded content may not be private.
    const priv = document.getElementById("privacy");
    Array.from(priv.options).forEach(o => {
      if (o.value === "SELF_ONLY") {
        o.disabled = branded;
        o.textContent = branded
          ? "Only me (private) — unavailable for branded content"
          : PRIVACY_LABELS.SELF_ONLY;
      }
    });
    if (branded && privacy === "SELF_ONLY") {
      priv.value = "";
      priv.classList.add("unset");
    }

    // The disclosure label TikTok will apply.
    const lbl = document.getElementById("commercial-label");
    if (branded && brand) lbl.textContent = "Your video will be labelled \"Paid partnership\".";
    else if (branded)     lbl.textContent = "Your video will be labelled \"Paid partnership\".";
    else if (brand)       lbl.textContent = "Your video will be labelled \"Promotional content\".";
    else                  lbl.textContent = "Select at least one option below.";

    document.getElementById("commercial-err").textContent =
      (commercial && !brand && !branded)
        ? "Choose \"Your brand\", \"Branded content\", or both." : "";

    // Consent copy follows the declaration.
    const consent = document.getElementById("consent-text");
    if (branded) {
      consent.innerHTML = `By posting, you agree to TikTok's
        <a href="${BRANDED_URL}" target="_blank" rel="noopener">Branded Content Policy</a> and
        <a href="${MUSIC_URL}" target="_blank" rel="noopener">Music Usage Confirmation</a>.`;
    } else {
      consent.innerHTML = `By posting, you agree to TikTok's
        <a href="${MUSIC_URL}" target="_blank" rel="noopener">Music Usage Confirmation</a>.`;
    }

    // Publish stays disabled until the user has made every required choice.
    const caption = document.getElementById("caption").value.trim();
    let block = "";
    if (!caption) block = "Add a caption to continue.";
    else if (!document.getElementById("privacy").value) block = "Choose who can view this video to continue.";
    else if (commercial && !brand && !branded) block = "Complete the content disclosure to continue.";

    document.getElementById("publish-btn").disabled = !!block;
    document.getElementById("publish-block").textContent = block;
  },

  /* ---------------- publish (simulated) ---------------- */
  publish() {
    const v = LIBRARY.find(x => x.id === this.current);
    const privacy = document.getElementById("privacy").value;

    document.getElementById("status-caption").textContent = v.title;
    document.getElementById("status-nick").textContent = SANDBOX.creator_nickname;
    document.getElementById("status-avatar").src = SANDBOX.creator_avatar_url;
    document.getElementById("status-privacy").textContent =
      "Privacy: " + (PRIVACY_LABELS[privacy] || privacy);
    const sv = document.getElementById("status-video");
    sv.src = v.src || "";
    if (v.poster) sv.poster = v.poster;

    ["s-upload", "s-process", "s-done"].forEach(s => {
      document.getElementById(s).className = "step";
    });
    document.getElementById("status-note").classList.add("hidden");
    document.getElementById("status-close").classList.add("hidden");
    document.getElementById("status-title").textContent = "Posting to TikTok";

    this.closePost();
    document.getElementById("status-overlay").classList.remove("hidden");

    const step = (id, cls) => { document.getElementById(id).className = "step " + cls; };
    const tick = (id) => { document.getElementById(id).className = "step done";
                           document.getElementById(id).querySelector(".dot").textContent = "✓"; };

    step("s-upload", "active");
    setTimeout(() => { tick("s-upload"); step("s-process", "active"); }, 1900);
    setTimeout(() => {
      tick("s-process"); tick("s-done");
      document.getElementById("status-title").textContent = "Submitted to TikTok";
      document.getElementById("status-note").classList.remove("hidden");
      document.getElementById("status-close").classList.remove("hidden");
      this.posted.unshift({ id: v.id, when: "Just now" });
    }, 4600);
  },

  finish() {
    document.getElementById("status-video").pause();
    document.getElementById("status-overlay").classList.add("hidden");
    this.renderLibrary();
  },
};

App.init();
