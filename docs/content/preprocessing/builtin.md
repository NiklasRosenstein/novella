# Builtin tags

## Block tags

### `@anchor`

This tag can be used to mark a location in a Markdown file with a global identifier that can be linked
to using the `{@link}` inline tag. Depending on the Markdown parser that is targeted, the tag may not be
replaced by any content at all but the `{@link}` tag may instead resolve it from the Markdown header that
the tag is placed in front of.

Note that the tag does not need to be placed in front of a Markdown header, but if it is not, the anchor
name must be set explicitly, otherwise `{@link}`s to the anchor will render a placeholder name.

__Arguments__

    @anchor <anchor_id> [<name>]

__Example__

    @anchor examples
    # Examples

---

### `@cat`

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

---

## Inline tags

### `@link`

The `{@link}` inline tag is used to link to an anchor, potentially from another page. The anchor
name is placed as the name of the link, unless overwritten via the settings or the second link
argument.

__Arguments__

    {@link <anchor_id> [<text>]}

__Example__

    Check out the {@link examples}. Also check out the {@link faq FAQ}.
