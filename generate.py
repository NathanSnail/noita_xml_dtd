import os
import re
import sys
from dataclasses import dataclass
import json

PRIMARY_FILE = True

# these constants might need to be changed if your editor works differently to lemminx when generating hover docs, they are only used for hover info
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
    if ty == "Hex8":
        return [("", "Hex8")]
    if ty == "StatusEffectType":
        return [("", "GAME_EFFECT")]
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
    if ty == "std::string" or ty == "std_string" or ty == "VEC_OF_MATERIALS":
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
    if ty in config_types:
        return ty
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
    "BIOME_TYPE": "BIOME_PROCEDURAL",
    "FOG_OF_WAR_TYPE": "DEFAULT",
    "NOISE_TYPE": "IQ2_SIMPLEX1234",
    "GENERAL_NOISE": "SimplexNoise",
    "AUDIO_LAYER": "EFFECT_GAME",
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


COMPONENTS_WITH_MATERIALS = {
    "MaterialAreaCheckerComponent",
    "PhysicsImageShapeComponent",
    "MaterialSeaSpawnerComponent",
    "ItemAlchemyComponent",
    "AnimalAIComponent",
}


def get_type_for_sub_field(field_name: str, ty: str, component_name: str) -> str:
    if component_name == "ParticleEmitterComponent":
        if field_name == "color":
            return "Hex8"
    elif component_name == "GenomeDataComponent":
        if field_name == "herd_id":
            return "xs:string"
    elif component_name in COMPONENTS_WITH_MATERIALS:
        if "material" in field_name:
            return "xs:string"
    return ty


def render_sub_field(field: Field, suffix: str, ty: str, component_name: str) -> str:
    true_type = get_type_for_sub_field(field.name, ty, component_name)
    default = get_default_for_sub_field(field, true_type, component_name)
    return f"""
\t\t<xs:attribute name="{field.name}{suffix}" type="{true_type}" default="{default}">
\t\t\t<xs:annotation>
\t\t\t\t<xs:documentation><![CDATA[```cpp{NL}{render_field_cpp(field).replace("\t","")}{NL}```]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>"""[
        1:
    ]


def render_field(field: Field, component_name: str) -> tuple[str, str]:
    tys = get_xml_type(field.ty)
    if type(tys) is str:
        return (
            f'\t\t\t\t<xs:element name="{field.name}" type="{tys}" minOccurs="0"/>',
            "",
        )
    if len(tys) == 0:
        return "", f"\t\t<!-- Some Unknown Type: {field.ty} for {field.name} -->"
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
\t<xs:complexType name="{comp.name}" mixed="true">
\t\t<xs:annotation> <xs:documentation> <![CDATA[{render_component_cpp(comp)}]]> </xs:documentation> </xs:annotation>{f"""
\t\t\t<xs:all>
{"\n".join(objects)}
\t\t\t</xs:all>""" if len(objects) != 0 else ""}{
"\n" + "\n".join(attrs) if len(attrs) != 0 else ""}
\t\t<xs:attributeGroup ref="CommonComponentAttributes"/>
\t</xs:complexType>"""[
        1:
    ]


def render_config(config: Component) -> str:
    fields = [render_field(x, config.name) for x in config.fields]
    attrs = [x[1] for x in fields if x[1] != ""]
    objects = [x[0] for x in fields if x[0] != ""]
    return f"""
\t<xs:complexType name="{config.name}" mixed="true">
\t\t<xs:annotation> <xs:documentation> <![CDATA[{render_component_cpp(config)}]]> </xs:documentation> </xs:annotation>{f"""
\t\t\t<xs:all>
{"\n".join(objects)}
\t\t\t</xs:all>""" if len(objects) != 0 else ""}{
"\n" + "\n".join(attrs) if len(attrs) != 0 else ""}
\t</xs:complexType>"""[
        1:
    ]


def trim_end(s: str):
    while s[-1] == " ":
        s = s[:-1]
    return s


# configs are identical to components really, so we can just reuse component code
configs_json = json.load(
    open("./config_betas.json", "r")
)  # credits to dexter for getting these, from https://github.com/dextercd/Noita-Component-Explorer/blob/main/data/configs_beta.json
configs: list[Component] = []
config_types = set()
for config in configs_json:
    configs.append(
        Component(
            config["name"].split("::")[-1],
            [
                Field(
                    field["name"], field["type"], "-", "", field.get("description", "")
                )
                for field in config.get("members", [])
                + config.get("privates", [])
                + config.get("custom_data_types", [])
                + config.get("objects", [])
            ],
        )
    )
    config_types.add(config["name"])


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
    "scale": "vec2 scale = {.x = 1, .y = 1}; // A stretching factor, most components don't work with this",
}

out = f"""
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
\t<xs:simpleType name="NoitaBool">
\t\t<xs:restriction base="xs:string">
\t\t\t<xs:enumeration value="0" />
\t\t\t<xs:enumeration value="1" />
\t\t</xs:restriction>
\t</xs:simpleType>
\t<xs:simpleType name="Hex8">
\t\t<xs:restriction base="xs:string">
\t\t\t<xs:pattern value="[0-9A-Fa-f]{{8}}|0" />
\t\t\t</xs:restriction>
\t</xs:simpleType>
\t<xs:attributeGroup name="CommonComponentAttributes">
\t\t<xs:attribute name="_tags" type="xs:string" default="" />
\t\t<xs:attribute name="_enabled" type="NoitaBool" default="1" />
\t</xs:attributeGroup>
\t<xs:complexType name="Transform" mixed="true">
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
\t\t\t\t<xs:element name="Base" type="Base" />
\t\t\t\t<xs:element name="Transform" type="Transform" />
\t\t\t\t{"\n\t\t\t\t".join([f"<xs:element name=\"{comp.name}\" type=\"{comp.name}\" />" for comp in components])}
\t\t\t</xs:choice>
\t\t</xs:sequence>
\t\t<xs:attribute name="name" type="xs:string" />
\t\t<xs:attribute name="tags" type="xs:string" />
\t\t<xs:attribute name="serialize" type="NoitaBool" default="1" />
\t</xs:complexType>
\t<xs:element name="Entity" type="EntityBase">
\t\t<xs:annotation>
\t\t\t<xs:documentation>Represents an entity that can be loaded into the world</xs:documentation>
\t\t</xs:annotation>
\t</xs:element>
\t<xs:complexType name="Base">
\t\t<xs:annotation>
\t\t\t<xs:documentation>Base file</xs:documentation>
\t\t</xs:annotation>
\t\t<xs:complexContent>
\t\t\t<xs:extension base="EntityBase">
\t\t\t\t<xs:attribute name="file" type="xs:string" use="required"/>
\t\t\t\t<xs:attribute name="include_children" type="NoitaBool"/>
\t\t\t</xs:extension>
\t\t</xs:complexContent>
\t</xs:complexType>
"""[
    1:
]
out += "\n".join([render_config(config) for config in configs])
out += "\n"
out += "\n".join([render_component(component) for component in components])
# out = out.replace("\t","").replace("\n","")


def replace_metatag(src: str, replacement: str, tag: str) -> str:
    parts = src.split(tag)
    # Replace content between markers
    for i in range(
        1, len(parts), 2
    ):  # Only replace in "odd" indexed parts (between markers)
        parts[i] = replacement
    # Rejoin the parts
    return tag.join(parts)


def prune_builtin(src: str) -> str:
    return "\n".join(
        "\n".join([x for x in src.split("\n") if x != ""][1:-1]).split(
            "<!--Builtin-->"
        )[0::2]
    )


open("entity.xsd", "w").write(out + "\n</xs:schema>")

# Update materials.xsd
material_attributes_json = json.load(open("./materials_attributes.json", "r"))
name_field = Field(
    "name",
    "std::string",
    "-",
    "",
    "Internal name, should be unique, otherwise will overwrite materials.",
)
material_fields = [name_field]
material_attributes = f"""\n\t\t<xs:attribute name="name" type="xs:string" use="required">
\t\t\t<xs:annotation>
\t\t\t\t<xs:documentation><![CDATA[{"```cpp" + NL + render_field_cpp(name_field).replace("\t","") + NL + "```"}]]></xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
"""
for attribute in material_attributes_json:
    ty = get_xml_type(attribute["type"])[0][1]
    this_field = Field(
        attribute["name"],
        attribute["type"],
        attribute["default"],
        "",
        attribute.get("doc", ""),
    )
    material_fields.append(this_field)
    doc = f"""<![CDATA[{"```cpp" + NL + render_field_cpp(this_field).replace("\t", "") + NL + "```"}]]>"""
    material_attributes += f"""\t\t<xs:attribute name="{attribute["name"]}" type="{ty}" default="{attribute["default"]}">
\t\t\t<xs:annotation>
\t\t\t\t<xs:documentation>{doc}</xs:documentation>
\t\t\t</xs:annotation>
\t\t</xs:attribute>
"""

material_xsd = replace_metatag(
    open("materials_source.xsd", "r").read(),
    material_attributes,
    "<!-- Material Attributes -->",
)
material_xsd = replace_metatag(
    material_xsd,
    "<xs:annotation><xs:documentation><![CDATA["
    + NL
    + render_component_cpp(Component("CellData", material_fields))
    .replace("\n", NL)
    .replace("\t", TAB)
    + NL
    + "]]></xs:documentation></xs:annotation>",
    "<!-- Material Docs -->",
)

config_explosion = next(
    render_config(config) for config in configs if config.name == "ConfigExplosion"
)
config_damage_critical = next(
    render_config(config) for config in configs if config.name == "ConfigDamageCritical"
)
material_xsd = replace_metatag(
    material_xsd,
    f"""
{config_damage_critical}
{config_explosion}
""",
    "<!-- ConfigExplosion -->",
)

open("./materials.xsd", "w").write(material_xsd)

# Merge files
out += prune_builtin(material_xsd)
with open("./sprite.xsd", "r") as sprite_file:
    out += prune_builtin(sprite_file.read())

open("merged.xsd", "w").write(out + "\n</xs:schema>")
