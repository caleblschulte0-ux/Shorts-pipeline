---
title: Privacy Policy
---

# Privacy Policy

_Last updated: May 31, 2026_

This Privacy Policy describes how the Shorts Pipeline ("we", "our", or
"the service"), operated by Caleb Schulte, collects, uses, and discloses
information in connection with the automated publication of short-form
video content to third-party social platforms.

## Information We Process

The Shorts Pipeline is an automated content-publishing tool. It does
not collect, store, or process personal information from end users of
the published videos. The service operates on the following data:

- **Public news content** retrieved from publicly accessible sources
  (Google Trends RSS, BBC News RSS, NPR, Hacker News, Reddit).
- **Public images** retrieved from Wikipedia/Wikimedia Commons and
  publicly licensed stock-video providers (Pexels, Pixabay).
- **Authentication tokens** for third-party platform APIs (YouTube,
  TikTok, Meta), stored as encrypted GitHub Actions secrets and used
  solely to upload generated videos to those platforms under the
  account owner's authorization.

We do not collect, store, sell, or share data about viewers of the
videos we publish. We have no access to viewer analytics beyond what
the host platforms (YouTube, TikTok, etc.) make available to the
account owner.

## How We Use Information

The authentication tokens described above are used exclusively to:

- Upload videos to the account owner's connected social media accounts.
- Set basic metadata (title, description, hashtags, scheduled publish
  time) on those uploads.

We do not use these tokens to read direct messages, access follower
information, modify account settings, or post anything other than the
generated video content.

## Third-Party Services

The pipeline interacts with the following third-party APIs:

- YouTube Data API v3
- TikTok Content Posting API
- Meta Graph API (Instagram / Facebook Reels)
- Groq API (for trending topic ranking)
- Pexels API and Pixabay API (for stock footage)

Each of these services has its own privacy policy governing data
collected through their APIs. We recommend reviewing those policies
on the respective providers' websites.

## Data Retention

The pipeline retains:

- Generated video files temporarily on the build server, deleted after
  upload.
- A log of published video URLs and titles in a public GitHub
  repository.
- No personal data about content viewers.

## Children's Privacy

The Shorts Pipeline does not knowingly publish content directed at
children under 13 and does not collect any data from children.

## Changes to This Policy

This policy may be updated. Updates will be posted at this URL with a
revised "Last updated" date.

## Contact

For questions about this policy, contact: caleblschulte0@gmail.com
