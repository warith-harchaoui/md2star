# Image handling fixture

Two image categories are exercised by this fixture:

## 1. Local relative-path image

The repository ships an image at `../../assets/logo.png`. With
`preprocess_markdown` running its `absolutize` phase, the relative
path is rewritten to an absolute one before Pandoc sees it — so the
conversion succeeds regardless of the working directory the user
invoked md2star from.

![md2star logo](../../assets/logo.png)

## 2. Remote URL — must be left in place by default

Without `--allow-remote-images`, md2star refuses to download the
following URL and leaves the markdown reference in place. With the
flag (or `--offline` + the flag — the offline override wins), the
behavior differs. The integration test asserts both branches.

![upstream banner](https://example.invalid/banner.png)
