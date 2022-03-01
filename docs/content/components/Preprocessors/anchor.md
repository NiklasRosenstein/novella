---
title: '@anchor and \{@link}'
---

This built-in tag preprocessor provides the `@anchor` and `\{@link}` tags that can be used to mark locations in a
Markdown file and link to them across files.

## `@anchor`

__Arguments__

    @anchor <anchor_id> [<name>]

__Example__

    @anchor examples
    # Examples

## `\{@link}`

The `\{@link}` inline tag is used to link to an anchor, potentially from another page. The anchor
name is placed as the name of the link, unless overwritten via the settings or the second link
argument.

__Arguments__

    \{@link <anchor_id> [<text>]}

__Example__

    Check out the \{@link examples}. Also check out the \{@link faq FAQ}.
