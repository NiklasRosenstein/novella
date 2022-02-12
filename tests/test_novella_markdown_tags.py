
from novella.markdown.tags import Tag, parse_tags, replace_tags


def test_parse_tags():
  assert list(parse_tags('''
Hello, World!

@cde
  Spam and eggs
    And more things
  And more

    # Code block here

Normal content

@abc Foobar
''')) == [
  Tag('cde', '\nSpam and eggs\n  And more things\nAnd more', 3, 6),
  Tag('abc', ' Foobar', 12, 12),
]


def test_replace_tags():
  def _repl(t: Tag) -> str:
    print(t)
    return ' '.join(t.args.split())
  assert replace_tags('''
@cdef Hello World!

@abc Foo
  Bar
    Baz
  Bazinga

    @not a tag''', _repl) == '''
Hello World!

Foo Bar Baz Bazinga

    @not a tag'''
