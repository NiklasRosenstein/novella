# Concepts

There are three relevant concepts for the configuration that are provided by
Novella itself:

1. {@link docs:novella:concepts:options}
2. {@link docs:novella:concepts:actions}
3. {@link docs:novella:concepts:templates}


@anchor docs:novella:concepts:options
## Options

An option is defined using the `NovellaContext.option()` function and allows you to define a command-line option that
is parsed by Novella when running your build script.

```py
option
  "site_directory" "d"
  description: "The directory in which to generate the final HTML."
  default: "_site"
```

@anchor docs:novella:concepts:actions
## Actions

Actions are plugins that execute some logic when its their turn and are declared using the `NovellaContext.do()`
function. Inside the configuration closure of actions, the `NovellaContext.options` dictionary can be used to
read option values that have been passed via the CLI.

```py
do "copy-files" {
  paths = [ "content", "mkdocs.yml" ]
}
```

Every action has a name, and by default that name will be the name of the action type ID that is the first argument
to the `do()` method. You can override this name using the `name` keyword argument. The name can be used to access
the action at a later point in the build script using the `NovellaContext.action()` method.

```py
template "mkdocs"

action "preprocess-markdown" {  # This action was created by the mkdocs template
  use "pydoc"  # Make use of the pydoc preprocessor plugin (note: requires Pydoc-Markdown)
}
```

!!! note

    New actions can be implemented using the `novella.action.Action` base class and registering the subclass under
    the `novella.actions` entrypoint.

Users can also create action logic on-the-fly by passing a closure to the `do()` method instead of an action ID.
The dependencies of the action can be managed from the configuration closure. Actions created this way need to
have a `name` set explicitly.

```py
# ...

def api_pages = {
  "Configuration": "my_package.config",
  "Client": "my_package.client",
}

# Generate some files in the build directory (here by the variable "directory" which is available
# through the Novella build context exposed in the action closure).
do
  name: "generate-api-pages"
  closure: {
    precedes "preprocess-markdown"
  }
  action: {
    for title, package in api_pages.items():
      def filename = directory / 'content' / 'api' / (package + '.md')
      filename.parent.mkdir(parents=True, exist_ok=True)
      filename.write_text('---\ntitle: {}\n---\n@pydoc {}\n'.format(title, package))
  }
```

@anchor docs:novella:concepts:templates
## Templates

A template is a plugin that takes over definition of the Novella pipeline to avoid some boilerplate in your
configuration script. Templates are invoked via the `NovellaContext.template()` function and can also be
configured using "init" and "post" closures (before the template is executed and after, respectively). Novella
itself delivers an `mkdocs` template out of the box.

```py
template "mkdocs"

action "mkdocs-update-config" {
  apply_defaults = False
}
```

!!! note

    New templates can be implemented using the `novella.template.Template` base class and registering the subclass
    under the `novella.templates` entrypoint.
