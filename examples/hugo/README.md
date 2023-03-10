# Novella + Hugo

This example was bootstrapped with

    $ hugo site new .
    $ git submodule add https://github.com/theNewDynamic/gohugo-theme-ananke themes/ananke
    $ echo "theme = 'ananke'" >> config.toml
    $ hugo new posts/my-first-post.md

Run Novella like this to display the page interactively, and to include drafts:

    $ novella --serve --drafts
