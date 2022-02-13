<%!

  import typing as t
  from docspec import ApiObject, HasMembers, Data, Function
  from docspec_python import format_arglist as _format_arglist

  def format_arglist(obj: Function, type_hints: bool = True) -> str:
    return _format_arglist(obj.args, type_hints)

  def get_fqn(obj: ApiObject) -> str:
    return '.'.join(x.name for x in obj.path)

  def get_type(obj: t.Any) -> str:
    return type(obj).__name__

  def get_attributes(obj: HasMembers) -> list[Data | Function]:
    members = []
    for member in obj.members:
      # TODO (@NiklasRosenstein): Identify properties
      if isinstance(member, Data):
        members.append(member)
    return members

  def get_functions(obj: HasMembers) -> list[Function]:
    members = []
    for member in obj.members:
      # TODO (@NiklasRosenstein): Exclude properties
      if isinstance(member, Function):
        members.append(member)
    return members

  def ignored(obj: ApiObject, parent: ApiObject | None, options: t.Mapping) -> bool:
    if options['exclude_undocumented'] and not obj.docstring and parent:
      return True
    return False

%>

<%def name="markdown_header(prefix, header_level, absolute_fqn=None)">
<%
  name = get_fqn(obj) if absolute_fqn or (absolute_fqn is None and options.absolute_fqn) else obj.name
  line = '#' * header_level + f'{prefix} `{name}`'
  #register_header(line, obj)
%>
${line}
</%def>

<%def name="definition_codeblock(obj)">
<%
  if get_type(obj) == 'Class':
    bases = '(' + ", ".join(obj.bases or []) + ')' if obj.bases else ''
    line = f'class {obj.name}{bases}: ...'
  elif get_type(obj) == 'Function':
    return_type = (' -> ' + obj.return_type) if obj.return_type and options.render_func_typehints else ''
    line = f'def {obj.name}({format_arglist(obj, options.render_func_typehints)}){return_type}: ...'
  elif get_type(obj) == 'Data':
    if not obj.datatype:
      return
    line = f'{obj.name}: {obj.datatype}'
  else:
    return
%>
```python
% for dec in getattr(obj, 'decorations', None) or []:
@${dec.name}${dec.args or ''}
% endfor
${line}
```
</%def>
