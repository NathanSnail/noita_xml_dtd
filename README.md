# Noita XML XSD
Contains xsd definitions for autocomplete and type checking in xml files for Noita.
Currently supports entities, sprites, materials. The end goal is documentation for
100% of the xml schemas Noita supports.

In order to use this, link this xsd in your xml lsp, Noita does support this syntax:
```xml
<?xml-model href="merged.xsd" type="application/xml-xsd"?>
```
\- it's parser skips it. but linking it globally is better.
For Neovim this is how you'd configure it with nvim-lspconfig, the settings should
be the same in any editor though.
```lua
local servers = {
	lemminx = {
		settings = {
			xml = {
				fileAssociations = {
					{
						systemId = "/home/nathan/Documents/code/noita_xml_dtd/merged.xsd",
						pattern = "**/*.xml",
					},
				},
			},
		},
	},
}
```
