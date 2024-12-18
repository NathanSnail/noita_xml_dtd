import os
import re
import sys
from dataclasses import dataclass

PRIMARY_FILE = True
TAB = "&emsp;&emsp;&emsp;&emsp;"
NL = "<br>"


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


@dataclass
class Enum:
    name: str
    variants: list[str]


def xml_encode(s: str) -> str:
    return s.replace(">", "&gt;").replace("<", "&lt;")


def get_xml_type(ty: str) -> list[tuple[str, str]] | str:
    lens = "LensValue"
    unsigned = "unsigned"
    enum = "::Enum"
    if ty[-len(enum) :] == enum:
        return [("", ty[: -len(enum)])]
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


TYPE_DEFAULTS = {
    "ARC_TYPE": "MATERIAL",
    "VERLET_TYPE": "CHAIN",
    "PROJECTILE_TYPE": "PROJECTILE",
    "EXPLOSION_TRIGGER_TYPE": "ON_CREATE",
    "HIT_EFFECT": "NONE",
    "INVENTORY_KIND": "QUICK",
    "LUA_VM_TYPE": "SHARED_BY_MANY_COMPONENTS",
    "MOVETOSURFACE_TYPE": "ENTITY",
    "PARTICLE_EMITTER_CUSTOM_STYLE": "NONE",
    "JOINT_TYPE": "REVOLUTE_JOINT",
    "PathFindingComponentState": "",
    "TeleportComponentState": "",
}


def format_decimal(value: str) -> str:
    """Format a decimal string to remove scientific notation and trailing zeroes."""
    value_float = float(value)
    return f"{value_float:.15f}".rstrip("0").rstrip(".")


def get_default_for_sub_field(field: Field, ty: str, component_name: str) -> str:
    default = TYPE_DEFAULTS.get(ty)
    if default is not None:
        return default

    if ty == "GAME_EFFECT":
        return "ELECTROCUTION" if component_name == "GameEffectComponent" else "NONE"
    elif ty == "RAGDOLL_FX":
        return "NORMAL" if component_name == "ProjectileComponent" else "NONE"
    elif ty == "DAMAGE_TYPES":
        return (
            "DAMAGE_PHYSICS_HIT" if component_name == "AreaDamageComponent" else "NONE"
        )

    if field.default != "-":
        if ty == "xs:decimal":
            return format_decimal(field.default)
        return field.default

    return "0" if ty != "xs:string" else ""


def render_sub_field(field: Field, suffix: str, ty: str, component_name: str) -> str:
    default = get_default_for_sub_field(field, ty, component_name)
    return f"""
\t\t\t<xs:attribute name="{field.name}{suffix}" type="{ty}" default="{default}">
\t\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{render_field_cpp(field)}{NL}```]]></xs:documentation>
\t\t\t\t</xs:annotation>
\t\t\t</xs:attribute>"""[
        1:
    ]


def render_field(field: Field, component_name: str) -> tuple[str, str]:
    tys = get_xml_type(field.ty)
    if type(tys) is str:
        return (
            f"""\t\t\t<xs:sequence minOccurs="0"> <xs:element name="{field.name}" type="{tys}" /></xs:sequence>""",
            "",
        )
    if len(tys) == 0:
        return "", f"\t\t\t\t<!-- Some Unknown Type: {field.ty} for {field.name} -->"
    return "", "\n".join(
        [render_sub_field(field, suffix, ty, component_name) for suffix, ty in tys]
    )


def render_field_cpp(comp: Field) -> str:
    return f"\t{comp.ty} {comp.name}{f" = {comp.default if comp.ty != "std::string" else f'"{comp.default}"'}" if comp.default != "-" else ""};{f" // {comp.values} {comp.comment}" if comp.values != "" or comp.comment != "" else ""}"


def render_component_cpp(comp: Component) -> str:
    out = f"```cpp\nclass {comp.name} {{\n"
    out += "\n".join([render_field_cpp(field) for field in comp.fields])
    out += "\n};\n```"
    return out.replace("\n", NL).replace("\t", TAB)  # parser bug


def render_component(comp: Component) -> str:
    fields = [render_field(x, comp.name) for x in comp.fields]
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
    if example == "[0, 1]":
        example = ""  # these are almost always wrong
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

enums: list[Enum] = []
enum_content = (
    open("./enum_src", "r").read().split("\n")
)  # this was generated from ghidra
for i in range(len(enum_content) // 2):
    name = enum_content[i * 2]
    fields = enum_content[i * 2 + 1][3:-2].split("', u'")
    enums.append(Enum(name, fields))
enums.append(Enum("PathFindingComponentState", [""]))
enums.append(Enum("TeleportComponentState", [""]))


def render_enum(enum: Enum) -> str:
    return f"""
\t<xs:simpleType name="{enum.name}">
\t\t<xs:restriction base="xs:string">
{"\n".join([f'\t\t\t<xs:enumeration value="{variant}"/>' for variant in enum.variants])}
\t\t</xs:restriction>
\t</xs:simpleType>"""[
        1:
    ]


transform = {
    "rotation": "float rotation = 0; // [0, 360] Measured in degrees",
    "position": "vec2 position; // EntityLoad doesn't respect this on entities, mostly used for relative offsets in InheritTransformComponent",
    "scale": "vec2 scale = {{.x = 1, .y = 1}}; // A stretching factor, most components don't work with this",
}

out = f"""
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
\t<xs:simpleType name="NoitaBool">
\t\t<xs:restriction base="xs:string">
\t\t\t<xs:enumeration value="0" />
\t\t\t<xs:enumeration value="1" />
\t\t</xs:restriction>
\t</xs:simpleType>
\t<xs:complexType name="Transform">
\t\t<xs:annotation>
\t\t\t<xs:documentation><![CDATA[```cpp{NL}class types::xform {{{NL}{TAB}{transform["position"]}{NL}{TAB}{transform["scale"]}{NL}{TAB}{transform["rotation"]}{NL}}};```]]></xs:documentation>
\t\t</xs:annotation>
\t\t<xs:attribute name="position.x" type="xs:decimal" default="0" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{transform["position"]}{NL}```]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="position.y" type="xs:decimal" default="0" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{transform["position"]}{NL}```]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="scale.x" type="xs:decimal" default="1" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{transform["scale"]}{NL}```]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="scale.y" type="xs:decimal" default="1" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{transform["scale"]}{NL}```]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t\t<xs:attribute name="rotation" type="xs:decimal" default="0" >
\t\t\t<xs:annotation>
\t\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{transform["rotation"]}{NL}```]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
\t</xs:complexType>
\t{"\n".join([render_enum(enum) for enum in enums])}
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
\t\t\t\t\t<xs:attribute name="file" type="xs:string" use="required"/>
\t\t\t\t</xs:extension>
\t\t\t</xs:complexContent>
\t\t</xs:complexType>
\t</xs:element>
"""[
    1:
]
out += "\n".join([render_component(component) for component in components])
# Sprite, might need some description on hover later, also some defaults are unknown
out += f"""
\t<xs:element name="Sprite">
\t\t<xs:complexType mixed="true">
\t\t\t<xs:choice maxOccurs="unbounded" minOccurs="0">
\t\t\t\t<xs:element name="RectAnimation" minOccurs="0" maxOccurs="unbounded">
\t\t\t\t\t<xs:complexType mixed="true">
\t\t\t\t\t\t<xs:choice>
\t\t\t\t\t\t\t<xs:element name="Event" minOccurs="0" maxOccurs="unbounded">
\t\t\t\t\t\t\t\t<xs:complexType mixed="true">
\t\t\t\t\t\t\t\t\t<xs:attribute name="name" type="xs:string" use="required" />
\t\t\t\t\t\t\t\t\t<xs:attribute name="frame" type="xs:nonNegativeInteger" use="required" />
\t\t\t\t\t\t\t\t\t<xs:attribute name="max_distance" type="xs:positiveInteger" />
\t\t\t\t\t\t\t\t\t<xs:attribute name="probability" type="xs:decimal" />
\t\t\t\t\t\t\t\t\t<xs:attribute name="on_finished" type="NoitaBool" />
\t\t\t\t\t\t\t\t\t<xs:attribute name="check_physics_material" type="NoitaBool" />
\t\t\t\t\t\t\t\t</xs:complexType>
\t\t\t\t\t\t\t</xs:element>
\t\t\t\t\t\t</xs:choice>
\t\t\t\t\t\t<xs:attribute name="name" type="xs:string" use="required" />
\t\t\t\t\t\t<xs:attribute name="frame_count" type="xs:positiveInteger" use="required" />
\t\t\t\t\t\t<xs:attribute name="frames_per_row" type="xs:positiveInteger" use="required" />
\t\t\t\t\t\t<xs:attribute name="frame_width" type="xs:positiveInteger" use="required" />
\t\t\t\t\t\t<xs:attribute name="frame_height" type="xs:positiveInteger" use="required" />
\t\t\t\t\t\t<xs:attribute name="frame_wait" type="xs:decimal" use="required" />
\t\t\t\t\t\t<xs:attribute name="pos_x" type="xs:integer" default="0" />
\t\t\t\t\t\t<xs:attribute name="pos_y" type="xs:integer" default="0" />
\t\t\t\t\t\t<xs:attribute name="offset_x" type="xs:decimal" default="0" />
\t\t\t\t\t\t<xs:attribute name="offset_y" type="xs:decimal" default="0" />
\t\t\t\t\t\t<xs:attribute name="shrink_by_one_pixel" type="NoitaBool" />
\t\t\t\t\t\t<xs:attribute name="has_offset" type="NoitaBool" default="1" />
\t\t\t\t\t\t<xs:attribute name="loop" type="NoitaBool" default="0" />
\t\t\t\t\t\t<xs:attribute name="next_animation" type="xs:string" default="" />
\t\t\t\t\t</xs:complexType>
\t\t\t\t</xs:element>
\t\t\t\t<xs:element name="Hotspot" minOccurs="0" maxOccurs="unbounded">
\t\t\t\t\t<xs:complexType mixed="true">
\t\t\t\t\t\t<xs:attribute name="name" type="xs:string" use="required" />
\t\t\t\t\t\t<xs:attribute name="color" type="xs:hexBinary" use="required" />
\t\t\t\t\t</xs:complexType>
\t\t\t\t</xs:element>
\t\t\t</xs:choice>
\t\t\t<xs:attribute name="filename" type="xs:string" use="required" />
\t\t\t<xs:attribute name="hotspots_filename" type="xs:string" />
\t\t\t<xs:attribute name="offset_x" type="xs:decimal" default="0" />
\t\t\t<xs:attribute name="offset_y" type="xs:decimal" default="0" />
\t\t\t<xs:attribute name="default_animation" type="xs:string" default="default" />
\t\t\t<xs:attribute name="color_a" type="xs:decimal" default="1" />
\t\t\t<xs:attribute name="color_b" type="xs:decimal" default="1" />
\t\t\t<xs:attribute name="color_g" type="xs:decimal" default="1" />
\t\t\t<xs:attribute name="color_r" type="xs:decimal" default="1" />
\t\t</xs:complexType>
\t\t<xs:unique name="UniqueRectAnimationName">
\t\t\t<xs:selector xpath="RectAnimation" />
\t\t\t<xs:field xpath="@name" />
\t\t</xs:unique>
\t</xs:element>
"""
out += "\n</xs:schema>"
# out = out.replace("\t","").replace("\n","")
open("generated.xsd", "w").write(out)
