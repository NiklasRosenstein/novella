
from novella.markdown.tagparser import Tag, parse_block_tags, parse_inline_tags, replace_block_tags


def test_parse_block_tags():
  text = '''
Hello, World!

@cde
  Spam and eggs
    And more things
  And more

    # Code block here

Normal content

@abc Foobar
  Spam and eggs
'''

  tags = list(parse_block_tags(text))

  assert text[slice(*tags[0].offset_span)] == '''@cde
  Spam and eggs
    And more things
  And more
'''

  assert text[slice(*tags[1].offset_span)] == '''@abc Foobar
  Spam and eggs
'''

  assert tags == [
    Tag('cde', '\nSpam and eggs\n  And more things\nAnd more', {}, (16, 68), (3, 6)),
    Tag('abc', ' Foobar\nSpam and eggs', {}, (108, 136), (12, 13)),
  ]


def test_replace_block_tags():
  def _repl(t: Tag) -> str:
    print(t)
    return ' '.join(t.args.split())
  assert replace_block_tags('''
@cdef Hello World!

@abc Foo
  Bar
    Baz
  Bazinga

    @not a tag''', _repl) == '''
Hello World!

Foo Bar Baz Bazinga

    @not a tag'''


def test_parse_inline_tags():
  text = 'Hello {@link World :with{ a = "b" } } and here is a {@escaped tag \\} :with a = "b" }'
  tags = list(parse_inline_tags(text))

  assert text[slice(*tags[0].offset_span)] == '{@link World :with{ a = "b" } }'
  assert text[slice(*tags[1].offset_span)] == '{@escaped tag \\} :with a = "b" }'

  assert tags == [
    Tag('link', ' World ', {'a': 'b'}, (6, 37), (1, 1)),
    Tag('escaped', ' tag } ', {'a': 'b'}, (52, 84), (1, 1)),
  ]


def test_parse_inline_tags_broken():
  text = 'Hello {@bad to another {@link to this} or that.'
  tags =  list(parse_inline_tags(text))
  assert text[slice(*tags[0].offset_span)] == '{@link to this}'
  assert tags == [
    Tag('link', ' to this', {}, (23, 38), (1, 1))
  ]
