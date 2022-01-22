# novella-core

Novella allows you to easily generate Python API documentation. It is the successor of Pydoc-Markdown.

## Quickstart

At it's core, Novella just runs a sequence of actions specified in a `novella.yml` configuration file. A typical
Novella configuration performs the following steps: 1) discover and load the Python source code to extract API
docstrings, 2) process Markdown files to inject the API documentation, 3) invoke a static site generator tool
like MkDocs or Hugo.

```yml
# novella.yml
pipeline:
  - copy-files: { source: docs }
  - process-markdown:
      directory: docs
      plugins:
        - pydoc: { search-path: $gitdir/src }
        - smart: {}
  - mkdocs: {}
```
