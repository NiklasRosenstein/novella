# Markdown Preprocessing

Novella provides some built-in Markdown pre-processing functionality to replace tags with automatically generated
content. Tags are either specified as their own block written as `@tag <args>` or inline as `{@tag <args>}`. Block
tags can span multiple lines if the following lines are indented. Tags may have a TOML configuration following the
keyword `:with`.
