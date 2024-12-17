import os
import re
from dataclasses import dataclass


@dataclass
class Field:
    name: str
    ty: str
    default: str
    values: str
    comment: str


@dataclass
class Component:
    name: str
    fields: list[Field]


def do_var_line(line: str) -> Field:
    shift = 0
    ty = ""
    if line[27] == " ":
        ty = line[4:28].replace(" ", "")
    else:
        ty_part = line[4:].split(" ")[0]
        if "::Enum" in ty_part:
            ty = ty_part.split("::Enum")[0] + "::Enum"
        elif "*" in ty_part:
            ty = ty_part.split("*")[0] + "*"
        else:
            type_match = re.match("[A-Z_]+", ty_part)
            assert type_match is not None
            ty = type_match.group()
    line = line[4 + len(ty) :]
    shift += 4 + len(ty)
    while line[0] == " ":
        line = line[1:]
        shift += 1
    field = line.split(" ")[0]
    line = line[len(field) :]
    shift += len(field)
    default_match = re.search("[^ ]+", line.split('"')[0])
    assert default_match is not None
    default = default_match.group()
    line = line[len(default) + default_match.start() + 1 :]
    shift += len(default)
    example = ""
    if default != "-":
        example = line.split("]")[0] + "]"
        line = line[len(example) :]
        shift += len(example)
    comment = '"'.join(line.split('"')[1:-1])
    return Field(field, ty, default, example, comment)


docs_path = os.path.expanduser(
    "~/.local/share/Steam/steamapps/common/Noita/component_documentation.txt"
)
docs = open(docs_path, "r").read()
cur_type = ""
current_fields = []
components = []
for l in docs.split("\n"):
    if l == "":
        continue
    if l[:4] == "    ":
        current_fields.append(do_var_line(l))
    elif l[0] != " ":
        if cur_type != "":
            components.append(Component(cur_type, current_fields))
        cur_type = l

for component in components:
    print(component)
