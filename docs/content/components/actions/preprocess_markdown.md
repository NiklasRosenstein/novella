
Novella provides built-in Markdown preprocessing functionality to replace tags with automatically generated content.
Tags are either specified as their own block written as `@tag <args>` or inline as `\{@link <args>}`. Block tags can
span multiple lines if the following lines are indented. Tags may have a TOML configuration following the keyword
`:with`.

```py title="build.novella"
do "preprocess-markdown" {
  path = "content/"
  use "pydoc"  # Requires Pydoc-Markdown (see https://github.com/NiklasRosenstein/pydoc-markdown)
}
```

---

@pydoc novella.markdown.preprocessor.MarkdownPreprocessorAction

---

@pydoc novella.markdown.preprocessor.MarkdownPreprocessor
