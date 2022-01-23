# novella

Novella allows you to easily generate Python API documentation.

## Introduction

At it's core, Novella just runs a sequence of actions, called the "pipeline", in an isolated build directory. The
fundemantal actions that Novella can perform are

* Loading Python code
* Copying files and folders from the project directory
* Post processing Markdown files
* Invoking a static site generator like MkDocs

In YAML, this looks something like

```yaml
pipeline:
- python: { package: novella }
- copy-files: { source: docs }
- process-markdown: { directory: docs }
- mkdocs: { directory: docs, use-profile: default }
```

Novella now executes these actions when you invoke it with the `novella` command. Note that the `mkdocs`
action augments the CLI with a `--serve` and `--build` option, either of which must be present, otherwise
MkDocs is not invoked.

    $ novella --build

The Python API documentation is generated inline in existing Markdown files in your `docs/` source directory
where the `@pydoc <object_fqn>` tag is used (this is done by the `process-markdown` action using the `pydoc`
processor that is enabled by default). This allows you to specify exactly where in your original Markdown
documentation source the Python API will be injected.
