import os
import re
import sys
from dataclasses import dataclass

PRIMARY_FILE = True


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


def xml_encode(s: str) -> str:
    return s.replace(">", "&gt;").replace("<", "&lt;")


def get_xml_type(ty: str) -> list[tuple[str, str]] | str:
    lens = "LensValue"
    unsigned = "unsigned"
    if ty[: len(lens)] == lens:
        return get_xml_type(ty[len(lens) + 1 : -1])
    if ty == "float" or ty == "double":
        return [("", "xs:decimal")]
    if ty[:3] == "int":
        return [("", "xs:int")]
    if ty[: len(unsigned)] == unsigned or ty[:4] == "uint":
        return [("", "xs:unsignedInt")]
    if ty == "std::string":
        return [("", "xs:string")]
    if ty == "bool":
        return [("", "NoitaBool")]
    if ty == "vec2":
        return [
            (".x", "xs:decimal"),
            (".y", "xs:decimal"),
        ]
    if ty == "ivec2":
        return [
            (".x", "xs:int"),
            (".y", "xs:int"),
        ]
    if ty == "types::fcolor":
        return [
            (".r", "xs:decimal"),
            (".g", "xs:decimal"),
            (".b", "xs:decimal"),
            (".a", "xs:decimal"),
        ]
    if ty == "ValueRange":
        return [
            (".min", "xs:decimal"),
            (".max", "xs:decimal"),
        ]
    if ty == "ValueRangeInt":
        return [
            (".min", "xs:int"),
            (".max", "xs:int"),
        ]
    if ty == "types::aabb":
        return [
            (".min_x", "xs:decimal"),
            (".min_y", "xs:decimal"),
            (".max_x", "xs:decimal"),
            (".max_y", "xs:decimal"),
        ]
    if ty == "types::iaabb":
        return [
            (".min_x", "xs:int"),
            (".min_y", "xs:int"),
            (".max_x", "xs:int"),
            (".max_y", "xs:int"),
        ]
    # objects
    if ty == "types::xform":
        return "Transform"
    # defined to be invalid
    if ty in ["EntityID", "WormPartPositions"]:
        return []
    if "*" in ty:
        return []
    if "std::vector" in ty:
        return []
    if "VECTOR_" in ty:
        return []
    if "VEC_" in ty:
        return []
    # print(f"fail: {ty}")
    return []


def render_sub_field(field: Field, suffix: str, docs: str, ty: str) -> str:
    if field.default != "-":
        if ty == "xs:decimal":
            value = float(field.default)
            field.default = f"{value:.15f}".rstrip("0").rstrip(
                "."
            )  # This ensures no scientific notation
        default = field.default
    else:
        default = "" if ty == "xs:string" else "0"
    if docs != "" or field.comment != "":
        return f"""
\t\t\t<xs:attribute name="{field.name}{suffix}" type="{ty}" default="{default}">
\t\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp<br>{render_field_cpp(field)}<br>```]]></xs:documentation>
\t\t\t\t</xs:annotation>
\t\t\t</xs:attribute>"""[
            1:
        ]
    return f"""\t\t\t<xs:attribute name="{field.name}{suffix}" type="{ty}" default="{field.default if field.default != "-" else ("" if ty == "xs:string" else "0")}" />"""


def render_field(field: Field) -> tuple[str, str]:
    tys = get_xml_type(field.ty)
    if type(tys) is str:
        return (
            f"""\t\t\t<xs:sequence minOccurs="0"> <xs:element name="{field.name}" type="{tys}" /></xs:sequence>""",
            "",
        )
    if len(tys) == 0:
        return "", f"\t\t\t\t<!-- Some Unknown Type: {field.ty} for {field.name} -->"
    docs = ""
    if field.default != "-":
        docs = f"`{field.default}` - `{field.values}`"
    return "", "\n".join(
        [render_sub_field(field, suffix, docs, ty) for suffix, ty in tys]
    )


def render_field_cpp(comp: Field) -> str:
    return f"\t{comp.ty} {comp.name}{f" = {comp.default if comp.ty != "std::string" else f'"{comp.default}"'}" if comp.default != "-" else ""};{f" // {comp.values} {comp.comment}" if comp.values != "" or comp.comment != "" else ""}"


def render_component_cpp(comp: Component) -> str:
    out = f"```cpp\nclass {comp.name} {{\n"
    out += "\n".join([render_field_cpp(field) for field in comp.fields])
    out += "\n};\n```"
    return out.replace("\n", "<br>").replace(
        "\t", "&emsp;&emsp;&emsp;&emsp;"
    )  # parser bug


def render_component(comp: Component) -> str:
    fields = [render_field(x) for x in comp.fields]
    attrs = [x[1] for x in fields if x[1] != ""]
    objects = [x[0] for x in fields if x[0] != ""]
    return f"""
\t<xs:element name="{comp.name}">
\t\t<xs:annotation> <xs:documentation> <![CDATA[{render_component_cpp(comp)}]]> </xs:documentation> </xs:annotation>
\t\t<xs:complexType mixed="true">{"\n" + "\n".join(objects) if len(objects) != 0 else ""}
{"\n".join(attrs)}
\t\t\t<xs:attribute name="_tags" type="xs:string" default="" />
\t\t\t<xs:attribute name="_enabled" type="NoitaBool" default="1" />
\t\t</xs:complexType>
\t</xs:element>"""[
        1:
    ]


def trim_end(s: str):
    while s[-1] == " ":
        s = s[:-1]
    return s


def do_var_line(line: str) -> Field:
    shift = 0
    ty = ""
    if line[27] == " ":
        ty = trim_end(line[4:28])
        if "unsigned" in ty:
            print(ty)
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


docs_path = (
    sys.argv[1]
    if len(sys.argv) > 1
    else (
        os.path.expanduser(
            "~/.local/share/Steam/steamapps/common/Noita/component_documentation.txt"
        )
        if PRIMARY_FILE
        else "./small_comp_docs.txt"
    )
)
docs = open(docs_path, "r").read()
cur_type = ""
current_fields = []
components: list[Component] = []


def flush_cur():
    global cur_type
    global current_fields
    global components
    if cur_type == "":
        return
    components.append(Component(cur_type, current_fields))
    current_fields = []
    cur_type = ""


for l in docs.split("\n"):
    if l == "":
        flush_cur()
        continue
    if l[:4] == "    ":
        current_fields.append(do_var_line(l))
    elif l[0] != " ":
        if cur_type != "":
            flush_cur()
        cur_type = l

out = f"""
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
\t<xs:simpleType name="NoitaBool">
\t\t<xs:restriction base="xs:string">
\t\t\t<xs:enumeration value="0" />
\t\t\t<xs:enumeration value="1" />
\t\t</xs:restriction>
\t</xs:simpleType>
\t<xs:complexType name="Transform">
\t\t<xs:attribute name="position.x" type="xs:decimal" default="0" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation>`EntityLoad` doesn't respect this on entities, mostly used for relative offsets in `InheritTransformComponent`</xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="position.y" type="xs:decimal" default="0" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation>`EntityLoad` doesn't respect this on entities, mostly used for relative offsets in `InheritTransformComponent`</xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="scale.x" type="xs:decimal" default="1" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation>A stretching factor, most components don't work with this</xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="scale.y" type="xs:decimal" default="1" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation>A stretching factor, most components don't work with this</xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="rotation" type="xs:decimal" default="0" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation>Measured in degrees</xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t</xs:complexType>
\t<xs:complexType name="EntityBase">
\t\t<xs:sequence minOccurs="0">
\t\t\t<xs:choice maxOccurs="unbounded" minOccurs="0">
\t\t\t\t<xs:element ref="Entity" />
\t\t\t\t<xs:element ref="Base" />
\t\t\t\t<xs:element name="Transform" type="Transform" />
\t\t\t\t{"\n\t\t\t\t\t".join([f"<xs:element ref=\"{comp.name}\" />" for comp in components])}
\t\t\t</xs:choice>
\t\t</xs:sequence>
\t\t<xs:attribute name="name" type="xs:string"></xs:attribute>
\t\t<xs:attribute name="tags" type="xs:string"></xs:attribute>
\t</xs:complexType>
\t<xs:element name="Entity" type="EntityBase">
\t\t<xs:annotation>
\t\t\t<xs:documentation>Represents an entity that can be loaded into the world</xs:documentation>
\t\t</xs:annotation>
\t</xs:element>
\t<xs:element name="Base">
\t\t<xs:annotation>
\t\t\t<xs:documentation>Base file</xs:documentation>
\t\t</xs:annotation>
\t\t<xs:complexType>
\t\t\t<xs:complexContent>
\t\t\t\t<xs:extension base="EntityBase">
\t\t\t\t\t<xs:attribute name="file" type="xs:string" />
\t\t\t\t</xs:extension>
\t\t\t</xs:complexContent>
\t\t</xs:complexType>
\t</xs:element>
"""[
    1:
]
out += "\n".join([render_component(component) for component in components])
out += "\n</xs:schema>"
# out = out.replace("\t","").replace("\n","")
open("generated.xsd", "w").write(out)
