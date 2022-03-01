---
title: '@cat'
---

# `@cat`

This tag can be used to reference the content of another file relative to the current file in the
project directory or relative to the project root (i.e. where the `build.novella` file is located)
using an absolute path.

__Arguments__

    @cat <file> [:with <toml>]

__Example__

    @cat ../../../readme.md
    @cat /../readme.md :with slice_lines = "3:"

__Settings__

* `slice_lines` (str) &ndash; A slice indicator that is applied to lines in the referenced file.
