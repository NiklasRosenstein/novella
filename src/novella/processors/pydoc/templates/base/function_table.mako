## members, obj, options
<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

<table>
  <thead>
    <th>${"Function" if helpers.attr.get_type(obj) == 'Module' else "Methods"}</th>
    <th>Description</th>
  </thead>
  <tbody>
      % for member in members:
    <tr>
      <td><code>{@link ${member.name}}</code></td>
      <td>

${member.docstring.splitlines()[0] if member.docstring else ''}

</td>
    </tr>
      % endfor
  </tbody>
</table>
