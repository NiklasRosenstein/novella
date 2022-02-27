---
title: Home
---

@anchor docs:novella:home
# Welcome to the Novella documentation!

@cat ../../readme.md :with slice_lines = "2:-3"

## Introduction

  [Craftr-Dsl]: https://github.com/craftr-build/craftr-dsl/
  [script]: https://github.com/NiklasRosenstein/novella/blob/develop/docs/build.novella

The build process is described using a `build.novella` file using the [Craftr-Dsl][] configuration language,
which is (almost) a superset of Python. The `novella` program executes the script, exposes the {@link
docs:novella:concepts:options :with text = "options"} declared within to the command-line interface and
executes the pipeline.

```
{@shell novella -h}
```

!!! note

    The example above is the output for `novella -h` for the [script][] that generates this documentation. The
    `script` argument group contains the options exposed by the build script indirectly through the usage of the
    `mkdocs` template.
