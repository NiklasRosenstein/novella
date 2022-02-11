<%!

  import typing as t
  from docspec import ApiObject, Function
  from docspec_python import format_arglist as _format_arglist

  def format_arglist(obj: Function, type_hints: bool = False) -> str:
    return _format_arglist(obj.args, type_hints)

  def get_fqn(obj: ApiObject) -> str:
    return '.'.join(x.name for x in obj.path)

  def get_type(obj: t.Any) -> str:
    return type(obj).__name__

%>

<%def name="markdown_header(prefix, header_level=None, absolute_fqn=None)">
${'#' * (header_level or options.header_level)} ${prefix} `${get_fqn(obj) if absolute_fqn or (absolute_fqn is None and options.absolute_fqn) else obj.name}`
</%def>

<%def name="definition_codeblock(obj)">
<%
  if get_type(obj) == 'Class':
    prefix = 'class '
    suffix = ', '.join(obj.bases or [])
    if suffix:
      suffix = f'({suffix})'
  elif get_type(obj) == 'Function':
    prefix = 'def '
    suffix = f'({format_arglist(obj)})'
  elif get_type(obj) == 'Data':
    prefix = ''
    suffix = ' = ' + obj.value
  else:
    return
%>
```python
% for dec in obj.decorations or []:
@${dec.name}${dec.args or ''}
% endfor
${prefix}${obj.name}${suffix}: ...
```
</%def>
