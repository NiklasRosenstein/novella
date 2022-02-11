<%namespace name="helpers" file="${context['options'].templates.helpers}"/>

<table>
  <thead>
    <th>Attribute</th>
    <th>Type</th>
    <th>Description</th>
  </thead>
  <tbody>
      % for member in obj.members:
    <tr>
        % if helpers.attr.get_type(member) == 'Data':
      <td><code>{@link ${member.name}}</code></td>
      <td><code>${member.datatype or ''}</code></td>
      <td>

${member.docstring or ''}

</td>
        % endif
    </tr>
      % endfor
  </tbody>
</table>
