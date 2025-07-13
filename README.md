# Noita XML XSD
Contains xsd definitions for autocomplete and type checking in xml files for Noita.
Currently supports entities, sprites, materials. The end goal is documentation for
100% of the xml schemas Noita supports.

If you wish to make this apply to specific files, put the following code at the top of the file:
```xml
<?xml-model href="merged.xsd" type="application/xml-xsd"?>
```
\- Noita's XML parser skips it, but linking it globally is better.

## Instructions for adding to Visual Studio Code:
Install the XML extension by Red Hat
In the top bar of VSC, go to File>Preferences>Settings and search for XML under the Extensions dropdown
Open it up and scroll down to `Xml: File Associations` and click on `Edit in settings.json`
Add the XML definitions to the `"xml.fileAssociations"` table, it should look something like this:
```json
	"xml.fileAssociations": [
		{
			"systemId": "/home/modder/Documents/code/noita_xml_dtd/out/merged.xsd",
			"pattern": "**/*.xml"
		},
		{
			"systemId": "/home/modder/Documents/code/noita_xml_dtd/out/mod.xsd",
			"pattern": "**/mod.xml"
		}
	]
```
`/home/modder/Documents/code/noita_xml_dtd/out/` should of course be the filepath leading to where you have the related definition files.
You can modify the `"pattern"` if you would like to better specify which files the definitions will apply to


## Instructions for add to Neovim:
In Neovim this is how you'd configure it for lemminx with nvim-lspconfig, the general
approach should be applicable to any editor though.
```lua
local servers = {
	lemminx = {
		settings = {
			xml = {
				fileAssociations = {
					{
						systemId = "/home/modder/Documents/code/noita_xml_dtd/out/merged.xsd", -- path must be absolute
						pattern = "**/*.xml",
					},
					{
						systemId = "/home/modder/Documents/code/noita_xml_dtd/out/mod.xsd",
						pattern = "**/mod.xml",
					},
				},
			},
		},
	},
}
for k, v in pairs(servers) do
	vim.lsp.config[k] = v
end
```
