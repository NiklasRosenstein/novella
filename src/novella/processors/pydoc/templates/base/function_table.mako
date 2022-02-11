<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

<table>
  <thead>
    <th>${"Function" if helpers.attr.get_type(obj) == 'Module' else "Methods"}</th>
    <th>Description</th>
  </thead>
  <tbody>
      % for member in obj.members:
    <tr>
        % if helpers.attr.get_type(member) == 'Function':
      <td><code>{@link ${member.name}}</code></td>
      <td>

${member.docstring.splitlines()[0] if member.docstring else ''}

</td>
        % endif
    </tr>
      % endfor
  </tbody>
</table>
