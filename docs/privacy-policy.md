---
title: Privacy Policy
---

# Privacy Policy

_Last updated: June 2, 2026_

This Privacy Policy describes how the Shorts Pipeline ("we", "our", or
"the service"), operated by Caleb Schulte, collects, uses, and discloses
information in connection with the automated publication of short-form
video content to **YouTube** and other third-party social platforms.

## YouTube API Services

The Shorts Pipeline uses **YouTube API Services** to upload generated
short-form videos to a single YouTube channel owned by the operator.
By using this service the operator acknowledges and agrees to be
bound by:

- The [YouTube Terms of Service](https://www.youtube.com/t/terms)
- The [Google Privacy Policy](https://policies.google.com/privacy)

The pipeline's use of YouTube API Services complies with the
[YouTube API Services Developer Policies](https://developers.google.com/youtube/terms/developer-policies)
and the
[YouTube API Services Terms of Service](https://developers.google.com/youtube/terms/api-services-terms-of-service).

## Information We Process

The Shorts Pipeline is an automated content-publishing tool. It does
not collect, store, or process personal information from end users of
the published videos. The service operates on the following data:

- **Public news content** retrieved from publicly accessible sources
  (Google Trends RSS, BBC News RSS, NPR, Hacker News, Reddit).
- **Public images** retrieved from Wikipedia/Wikimedia Commons and
  publicly licensed stock-video providers (Pexels, Pixabay, Mixkit).
- **Authentication tokens** for third-party platform APIs (YouTube,
  TikTok, Meta), stored as encrypted GitHub Actions secrets and used
  solely to upload generated videos to those platforms under the
  account owner's authorization.
- **Aggregated public video statistics** (view, like, and comment
  counts) returned by the YouTube Data API for videos previously
  uploaded by the operator, used to inform future topic selection.
  No viewer identities or personally identifiable information are
  accessed.

We do not collect, store, sell, or share data about viewers of the
videos we publish.

## How We Use Information

The YouTube authentication token described above is used exclusively to:

- Upload videos to the operator's own YouTube channel.
- Set basic metadata (title, description, hashtags, scheduled publish
  time) on those uploads via the YouTube Data API.
- Read back public statistics (view, like, and comment counts) for
  videos the operator has uploaded.

We do not use the YouTube token to:

- Access viewer identities, comment-author identities, or any
  personally identifiable information.
- Read direct messages, modify channel settings, or post on other
  users' behalf.
- Sell, share, or transmit YouTube user data to any third party.

## Data Storage and Security

- The YouTube OAuth refresh token is stored as an encrypted GitHub
  Actions secret (`YOUTUBE_TOKEN_JSON`) accessible only to the
  authenticated GitHub Actions workflow runner.
- Short-lived access tokens are generated in-memory during workflow
  runs and discarded when the run completes.
- The pipeline source code is publicly auditable at
  [https://github.com/caleblschulte0-ux/Shorts-pipeline](https://github.com/caleblschulte0-ux/Shorts-pipeline).

## Data Retention and Deletion

The pipeline retains:

- A public log of uploaded video URLs and timestamps in the
  Shorts-pipeline GitHub repository.
- Aggregated view, like, and comment counts in
  `state/analytics/<date>.json` snapshots in the same repository.
- No personal data about viewers, comment authors, or other YouTube
  users at any time.

**Data deletion request**: any individual whose data may have been
inadvertently included may request deletion by emailing
caleblschulte0@gmail.com with the subject line
"Shorts Pipeline — Data Deletion Request". Requests will be honored
within 7 business days by removing the relevant entries from the
repository.

**Revoking YouTube access**: the operator may revoke the pipeline's
access to YouTube at any time by visiting
[https://myaccount.google.com/permissions](https://myaccount.google.com/permissions)
and removing the Shorts Pipeline application. Once revoked, the
pipeline will be unable to upload further videos or access any
YouTube data.

## Third-Party Services

The pipeline interacts with the following third-party APIs:

- **YouTube Data API v3** — governed by the
  [Google Privacy Policy](https://policies.google.com/privacy) and
  [YouTube Terms of Service](https://www.youtube.com/t/terms).
- TikTok Content Posting API
- Meta Graph API (Instagram / Facebook Reels)
- Groq API (for trending topic ranking)
- Pexels API, Pixabay API, Mixkit (for stock footage)

Each of these services has its own privacy policy governing data
collected through their APIs.

## Children's Privacy

The Shorts Pipeline does not knowingly publish content directed at
children under 13 and does not collect any data from children.

## Changes to This Policy

This policy may be updated. Updates will be posted at this URL with a
revised "Last updated" date.

## Contact

For questions about this policy, contact: caleblschulte0@gmail.com
