# novella

Novella allows you to easily generate Python API documentation.

## Introduction

At it's core, Novella just runs a sequence of actions, called the "pipeline", in an isolated build directory. Now,
usually the builtin actions are used to copy the Markdown files into an isolated build directory to then run a
Markdown preprocessor over them. Among the builtin preprocessors is one that allows you to embed Python API
documentation in Markdown format in the Markdown files.

The easiest way to get started is to make use of the Mkdocs template.

```python
# build.novella
template "mkdocs"
```

By default, it will assume that your documentation resides in a `docs/` folder next to a `src/` directory from
which your Python source code is loaded. Furthermore, it assumes that your documentation content for Mkdocs lies
in the `docs/content/` folder, next to the `mkdocs.yml`. It will also apply a template Mkdocs configuration on top
of your `mkdocs.yml` that makes use of `mkdocs-material` and enables various Markdown extensions. The template also
registers the command-line options `--serve` and `--site-dir,-d` that modify how Mkdocs is invoked, allowing you to
pass them along from the Novella CLI.

    $ python -m novella --serve

<details><summary>The template is effectively the same as using this Novella configuration instead (expand for details).</summary>

```python
option "serve", description="Use mkdocs serve", flag=True
option "site_dir", "d", description="Build directory (not with --serve)", default="_site"

do "copy-files" {
  paths = [ "src", "mkdocs.yml" ]
}

do "process-markdown" {
  use "pydoc" {
    loader.search_path = [ project_directory / "../src" ]
    options['module_after_header'] = True
  }
  use "cat"
}

do "run" {
  args = [ "mkdocs" ]
  if options.get("serve"):
    args = args + [ "serve" ]
  else:
    args = args + [ "build", "-d", project_directory / options.get("site_dir") ]
}
```
</details>

Now, in your the Markdown files in your `docs/content/` folder, you can make use of the `@pydoc` tag
to specify an absolute FQN for the Python API documentation that should be rendered in its place.

```md
# API Documentation

Here you can find the documentation for the most relevant pieces of the Novella API.

@pydoc novella.action.Action
```
